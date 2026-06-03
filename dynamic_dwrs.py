from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4
from ryu.lib import hub
import random

# ---------------- CONFIG ----------------
VIP = "10.0.0.100"
VIP_MAC = "00:00:00:00:00:99"

CLIENT_IP = "10.0.0.1"
SERVER_IPS = ["10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"]
DEFAULT_WEIGHTS = [1, 1, 1, 1]  

FLOW_IDLE_TIMEOUT = 40
MONITOR_INTERVAL = 10


class DWRSLoadBalancer(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(DWRSLoadBalancer, self).__init__(*args, **kwargs)

        self.datapaths = {}

        # learned mapping
        self.ip_to_port = {}    # ip → switch port
        self.ip_to_mac = {}     # ip → mac

        # weights
        self.weights = list(DEFAULT_WEIGHTS)
        self.cum_weights = self._build_cumulative(self.weights)

        hub.spawn(self._monitor)

    # ---------------------------------------------------------
    # Helper: build cumulative weights for binary search
    # ---------------------------------------------------------
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

        # binary search
        lo = -1
        hi = len(self.cum_weights) - 1
        while lo + 1 < hi:
            mid = (lo + hi) // 2
            if r <= self.cum_weights[mid]:
                hi = mid
            else:
                lo = mid
        return hi

    # ---------------------------------------------------------
    # Install OpenFlow rule
    # ---------------------------------------------------------
    def _add_flow(self, datapath, priority, match, actions, idle_timeout):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout
        )
        datapath.send_msg(mod)

    # ---------------------------------------------------------
    # Switch connected 
    # ---------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp

        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        # table-miss
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]

        self._add_flow(dp, 0, match, actions, idle_timeout=0)
        self.logger.info("Switch %s connected", dp.id)

    # ---------------------------------------------------------
    # Packet-In handler
    # ---------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofproto = dp.ofproto

        in_port = msg.match["in_port"]
        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(ethernet.ethernet)
        if eth.ethertype == 0x88cc:   # ignore LLDP
            return

        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        
        if eth:
            pass

        # -----------------------------------------------------
        # Handle ARP
        # -----------------------------------------------------
        if arp_pkt:
            src_ip = arp_pkt.src_ip
            src_mac = arp_pkt.src_mac

            self.ip_to_port[src_ip] = in_port
            self.ip_to_mac[src_ip] = src_mac

            # ARP request for VIP → respond with VIP MAC
            if arp_pkt.dst_ip == VIP:
                self.logger.info("Sending ARP reply for VIP")

                reply = packet.Packet()
                reply.add_protocol(ethernet.ethernet(
                    ethertype=eth.ethertype,
                    dst=eth.src,
                    src=VIP_MAC
                ))
                reply.add_protocol(arp.arp(
                    opcode=arp.ARP_REPLY,
                    src_mac=VIP_MAC,
                    src_ip=VIP,
                    dst_mac=arp_pkt.src_mac,
                    dst_ip=arp_pkt.src_ip
                ))
                reply.serialize()

                actions = [parser.OFPActionOutput(in_port)]
                out = parser.OFPPacketOut(
                    datapath=dp,
                    in_port=ofproto.OFPP_CONTROLLER,
                    actions=actions,
                    data=reply.data
                )
                dp.send_msg(out)
                return

            # else: flood ARP normally
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            out = parser.OFPPacketOut(
                datapath=dp,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=msg.data
            )
            dp.send_msg(out)
            return

        # -----------------------------------------------------
        # Handle IPv4
        # -----------------------------------------------------
        if ip_pkt:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst

            
            if src_ip == CLIENT_IP and dst_ip == VIP:

                # Ensure all server mappings known
                missing = [s for s in SERVER_IPS if s not in self.ip_to_port]
                if missing:
                    self.logger.info("Missing ARP for servers, flooding.")
                    actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    out = parser.OFPPacketOut(
                        datapath=dp,
                        buffer_id=msg.buffer_id,
                        in_port=in_port,
                        actions=actions,
                        data=msg.data)
                    dp.send_msg(out)
                    return

                # pick server
                idx = self._pick_server_index()
                server_ip = SERVER_IPS[idx]
                server_port = self.ip_to_port[server_ip]
                server_mac = self.ip_to_mac[server_ip]
                client_port = self.ip_to_port[CLIENT_IP]
                client_mac = self.ip_to_mac[CLIENT_IP]

                self.logger.info("LB decision: %s → %s", src_ip, server_ip)

                
                # Forward flow (client → VIP) → server
                
                match_fwd = parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_src=CLIENT_IP,
                    ipv4_dst=VIP
                )
                actions_fwd = [
                    parser.OFPActionSetField(ipv4_dst=server_ip),
                    parser.OFPActionSetField(eth_dst=server_mac),
                    parser.OFPActionSetField(eth_src=VIP_MAC),
                    parser.OFPActionOutput(server_port)
                ]
                self._add_flow(dp, 100, match_fwd, actions_fwd, FLOW_IDLE_TIMEOUT)

                # Reverse flow
                match_rev = parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_src=server_ip,
                    ipv4_dst=CLIENT_IP
                )
                actions_rev = [
                    parser.OFPActionSetField(ipv4_src=VIP),
                    parser.OFPActionSetField(eth_src=VIP_MAC),
                    parser.OFPActionSetField(eth_dst=client_mac),
                    parser.OFPActionOutput(client_port)
                ]
                self._add_flow(dp, 100, match_rev, actions_rev, FLOW_IDLE_TIMEOUT)

                
                actions_pkt = [
                    parser.OFPActionSetField(ipv4_dst=server_ip),
                    parser.OFPActionSetField(eth_dst=server_mac),
                    parser.OFPActionSetField(eth_src=VIP_MAC),
                    parser.OFPActionOutput(server_port)
                ]
                out = parser.OFPPacketOut(
                    datapath=dp,
                    buffer_id=msg.buffer_id,
                    in_port=in_port,
                    actions=actions_pkt,
                    data=msg.data
                )
                dp.send_msg(out)
                return

        # default: flood unknown
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        dp.send_msg(out)


    def _monitor(self):
        while True:
            self.cum_weights = self._build_cumulative(self.weights)
            hub.sleep(MONITOR_INTERVAL)