from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4
from ryu.lib import hub
import random
import statistics
import time

VIP = '10.0.0.100'
VIP_MAC = '00:00:00:00:00:FE'
CLIENT_IP = '10.0.0.1'
SERVER_IPS = ['10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5']

DEFAULT_WEIGHTS = [1, 1, 1, 1]
MONITOR_INTERVAL = 5.0
FLOW_IDLE_TIMEOUT = 30
LOAD_THRESHOLD = 0.5

class HybridDWRS(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(HybridDWRS, self).__init__(*args, **kwargs)
        self.datapaths = {}            # dpid -> datapath
        self.mac_to_port = {}          # dpid -> { mac: port }
        self.ip_to_port = {}           # ip -> port (learned)
        self.ip_to_mac = {}            # ip -> mac  (learned)
        self.weights = list(DEFAULT_WEIGHTS)
        self.cum_weights = self._build_cumulative(self.weights)
        self.method = 'static'         # 'static' or 'dynamic'
        self.server_loads = [0.0 for _ in SERVER_IPS]
        self.monitor_thread = hub.spawn(self._monitor)

    # ---------------- helpers ----------------
    def _build_cumulative(self, weights):
        cum = []
        s = 0
        for w in weights:
            s += w
            cum.append(s)
        return cum

    def _pick_server_index(self):
        total = self.cum_weights[-1]
        r = random.random() * total
        lw = -1
        up = len(self.cum_weights) - 1
        while lw + 1 < up:
            mid = (lw + up) // 2
            if r <= self.cum_weights[mid]:
                up = mid
            else:
                lw = mid
        return up

    def _add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst,
                                idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    def _delete_dynamic_flows(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        # delete flows matching server IPs or client (both directions)
        for ip in SERVER_IPS + [CLIENT_IP]:
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=ip)
            mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE,
                                    out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY,
                                    match=match)
            datapath.send_msg(mod)

    # ---------------- events ----------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Table-miss: send to controller for learning
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)

        self.mac_to_port.setdefault(datapath.id, {})
        self.logger.info("Switch %s connected (table-miss installed)", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        in_port = msg.match.get('in_port')

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if eth is None:
            return
        # ignore LLDP
        if eth.ethertype == 0x88cc:
            return

        # ensure mac table for this dpid
        self.mac_to_port.setdefault(dpid, {})
        # Learn L2
        self.mac_to_port[dpid][eth.src] = in_port

        # ARP handling: learn and optionally reply for VIP
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            # learn ip->mac and ip->port
            self.ip_to_mac[arp_pkt.src_ip] = arp_pkt.src_mac
            self.ip_to_port[arp_pkt.src_ip] = in_port

            if arp_pkt.opcode == arp.ARP_REQUEST and arp_pkt.dst_ip == VIP:
                # reply to ARP request for VIP with VIP_MAC
                self._reply_arp(datapath, in_port, arp_pkt.src_mac, arp_pkt.src_ip)
                return
            # otherwise do normal ARP forwarding (flood or directed)
            if arp_pkt.dst_ip in self.ip_to_port:
                out_port = self.ip_to_port[arp_pkt.dst_ip]
            else:
                out_port = ofproto.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=msg.data)
            datapath.send_msg(out)
            return

        # IPv4 handling
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt:
            # learn ip->mac and ip->port from IP packet as well
            self.ip_to_mac[ip_pkt.src] = eth.src
            self.ip_to_port[ip_pkt.src] = in_port

            # Only intercept traffic destined to VIP
            if ip_pkt.dst == VIP and ip_pkt.src == CLIENT_IP:
                # pick server according to current method
                if self.method == 'dynamic':
                    idx = self._pick_server_index()
                else:
                    # static selection: simple round-robin among servers (or you can use fixed weights)
                    idx = (int(time.time() / MONITOR_INTERVAL) % len(SERVER_IPS))
                server_ip = SERVER_IPS[idx]
                server_port = self.ip_to_port.get(server_ip)
                server_mac = self.ip_to_mac.get(server_ip)
                client_port = self.ip_to_port.get(CLIENT_IP)
                client_mac = self.ip_to_mac.get(CLIENT_IP)

                # if server mapping unknown, flood to learn ARP
                if server_port is None or server_mac is None:
                    self.logger.debug("Unknown server mapping for %s, flooding to learn", server_ip)
                    actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                              in_port=in_port, actions=actions, data=msg.data)
                    datapath.send_msg(out)
                    return

                self.logger.info("LB (%s): %s -> %s (idx=%d)", self.method, ip_pkt.src, server_ip, idx)

                # install forward flow: client->VIP -> rewrite dst and mac, output to server_port
                match = parser.OFPMatch(eth_type=0x0800, ipv4_src=CLIENT_IP, ipv4_dst=VIP)
                actions = [
                    parser.OFPActionSetField(ipv4_dst=server_ip),
                    parser.OFPActionSetField(eth_dst=server_mac),
                    parser.OFPActionOutput(server_port)
                ]
                self._add_flow(datapath, priority=200, match=match, actions=actions, idle_timeout=FLOW_IDLE_TIMEOUT)

                # install reverse flow: server->client -> rewrite src IP to VIP and set dst mac to client_mac
                if client_port is not None and client_mac is not None:
                    match_r = parser.OFPMatch(eth_type=0x0800, ipv4_src=server_ip, ipv4_dst=CLIENT_IP)
                    actions_r = [
                        parser.OFPActionSetField(ipv4_src=VIP),
                        parser.OFPActionSetField(eth_dst=client_mac),
                        parser.OFPActionOutput(client_port)
                    ]
                    self._add_flow(datapath, priority=200, match=match_r, actions=actions_r, idle_timeout=FLOW_IDLE_TIMEOUT)
                else:
                    # fallback reverse flow (flood) if client mapping missing
                    match_r = parser.OFPMatch(eth_type=0x0800, ipv4_src=server_ip, ipv4_dst=CLIENT_IP)
                    actions_r = [parser.OFPActionSetField(ipv4_src=VIP), parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    self._add_flow(datapath, priority=100, match=match_r, actions=actions_r, idle_timeout=FLOW_IDLE_TIMEOUT)

                # forward the current packet
                actions_pkt = [
                    parser.OFPActionSetField(ipv4_dst=server_ip),
                    parser.OFPActionSetField(eth_dst=server_mac),
                    parser.OFPActionOutput(server_port)
                ]
                out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                          in_port=in_port, actions=actions_pkt, data=msg.data)
                datapath.send_msg(out)
                return

        # Default L2 forwarding for everything else (critical for pingall)
        dst = eth.dst
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)

    # ---------------- monitor thread ----------------
    def _monitor(self):
        while True:
            
            if len(self.server_loads) > 0:
                avg = statistics.mean(self.server_loads)
                variance = statistics.variance(self.server_loads) if len(self.server_loads) > 1 else 0.0
                if variance > LOAD_THRESHOLD and self.method != 'dynamic':
                    self.method = 'dynamic'
                    for dp in self.datapaths.values():
                        self._delete_dynamic_flows(dp)
                    self.logger.info("Switched to dynamic (variance=%.3f)", variance)
                elif variance <= LOAD_THRESHOLD and self.method != 'static':
                    self.method = 'static'
                    for dp in self.datapaths.values():
                        self._delete_dynamic_flows(dp)
                    self.logger.info("Switched to static (variance=%.3f)", variance)
            hub.sleep(MONITOR_INTERVAL)

    # ---------------- utilities ----------------
    def _reply_arp(self, datapath, port, dst_mac, dst_ip):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        eth_reply = ethernet.ethernet(dst=dst_mac, src=VIP_MAC, ethertype=0x0806)
        arp_reply = arp.arp(opcode=arp.ARP_REPLY,
                            src_mac=VIP_MAC, src_ip=VIP,
                            dst_mac=dst_mac, dst_ip=dst_ip)
        pkt = packet.Packet()
        pkt.add_protocol(eth_reply)
        pkt.add_protocol(arp_reply)
        pkt.serialize()

        actions = [parser.OFPActionOutput(port)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=0xffffffff,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=pkt.data)
        datapath.send_msg(out)
        self.logger.debug("Replied ARP for VIP to %s (port %d)", dst_ip, port)