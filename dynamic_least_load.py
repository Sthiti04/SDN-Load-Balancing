from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4
from ryu.lib import hub

VIP = '10.0.0.100'
CLIENT_IP = '10.0.0.1'
SERVER_IPS = ['10.0.0.2', '10.0.0.3', '10.0.0.4', '10.0.0.5']

MONITOR_INTERVAL = 5.0      # seconds between monitoring rounds
FLOW_IDLE_TIMEOUT = 30      # seconds for installed flows

class LeastLoadLB(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(LeastLoadLB, self).__init__(*args, **kwargs)
        # datapath registry
        self.datapaths = {}

        # learning maps
        self.ip_to_port = {}   # ip -> switch port
        self.ip_to_mac = {}    # ip -> mac

        # port statistics tracking
        # structure: { dpid: { port_no: last_tx_bytes } }
        self.last_port_bytes = {}

        # most recent measured load (bytes/sec) per port: { dpid: { port_no: bytes_per_sec } }
        self.port_load = {}

        # server loads 
        self.server_loads = [0.0] * len(SERVER_IPS)

        # index of server selected at previous monitoring time (requests within interval go to this)
        self.current_target_idx = 0  # default first server

        # Start monitoring thread
        self.monitor_thread = hub.spawn(self._monitor)

    # ------------------ OFP/RYU event handlers ------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # table-miss: send to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=0, match=match, instructions=inst)
        datapath.send_msg(mod)

        
        self.last_port_bytes.setdefault(datapath.id, {})
        self.port_load.setdefault(datapath.id, {})
        self.logger.info("Switch %s connected, initialized stats.", datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        
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

        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        
        if arp_pkt:
            self.ip_to_port[arp_pkt.src_ip] = in_port
            self.ip_to_mac[arp_pkt.src_ip] = arp_pkt.src_mac
            # flood ARP to learn mapping across hosts (controller not acting as ARP responder)
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                      in_port=in_port, actions=actions, data=msg.data)
            datapath.send_msg(out)
            return

        if ip_pkt:
            # learn from ip packet
            self.ip_to_port[ip_pkt.src] = in_port
            self.ip_to_mac[ip_pkt.src] = eth.src

            
            if ip_pkt.src == CLIENT_IP and ip_pkt.dst == VIP:
                
                target_ip = SERVER_IPS[self.current_target_idx]
                target_port = self.ip_to_port.get(target_ip)
                target_mac = self.ip_to_mac.get(target_ip)
                client_port = self.ip_to_port.get(CLIENT_IP)

                if target_port is None or target_mac is None:
                    # If server mapping unknown, flood to trigger ARP learning
                    self.logger.debug("Target server mapping not found (%s); flooding to learn.", target_ip)
                    actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
                    out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                              in_port=in_port, actions=actions, data=msg.data)
                    datapath.send_msg(out)
                    return

                self.logger.info("LeastLoad: sending client %s -> server %s (idx=%d)",
                                 ip_pkt.src, target_ip, self.current_target_idx)

                # install forward flow
                match = parser.OFPMatch(eth_type=0x0800, ipv4_src=CLIENT_IP, ipv4_dst=VIP)
                actions = [
                    parser.OFPActionSetField(ipv4_dst=target_ip),
                    parser.OFPActionSetField(eth_dst=target_mac),
                    parser.OFPActionOutput(target_port)
                ]
                self._add_flow(datapath, priority=200, match=match, actions=actions, idle_timeout=FLOW_IDLE_TIMEOUT)

                # install reverse flow
                match_r = parser.OFPMatch(eth_type=0x0800, ipv4_src=target_ip, ipv4_dst=CLIENT_IP)
                actions_r = [
                    parser.OFPActionSetField(ipv4_src=VIP),
                    parser.OFPActionOutput(client_port if client_port is not None else ofproto.OFPP_FLOOD)
                ]
                self._add_flow(datapath, priority=200, match=match_r, actions=actions_r, idle_timeout=FLOW_IDLE_TIMEOUT)

                # forward current packet immediately
                actions_pkt = [
                    parser.OFPActionSetField(ipv4_dst=target_ip),
                    parser.OFPActionSetField(eth_dst=target_mac),
                    parser.OFPActionOutput(target_port)
                ]
                out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                          in_port=in_port, actions=actions_pkt, data=msg.data)
                datapath.send_msg(out)
                return

        # default: flood unknown packets
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)

    # ------------------ helper methods ------------------
    def _add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                match=match, instructions=inst, idle_timeout=idle_timeout)
        datapath.send_msg(mod)

    # ------------------ monitoring & stats ------------------
    def _monitor(self):
        
        while True:
            
            for dp in list(self.datapaths.values()):
                self._request_port_stats(dp)
            
            hub.sleep(0.5)

            
            loads = []
            for ip in SERVER_IPS:
                port = self.ip_to_port.get(ip)
                if port is None:
                    
                    loads.append(float('inf'))
                else:
                    
                    total_bytes_per_sec = 0.0
                    for dpid, portloads in self.port_load.items():
                        total_bytes_per_sec += portloads.get(port, 0.0)
                    loads.append(total_bytes_per_sec)

            
            if all(l == float('inf') for l in loads):
                self.logger.debug("No server port mappings known yet; keeping current target idx=%d",
                                  self.current_target_idx)
            else:
                
                numeric_loads = [l if l != float('inf') else 1e18 for l in loads]
                self.server_loads = numeric_loads
                
                min_idx = int(min(range(len(numeric_loads)), key=lambda i: numeric_loads[i]))
                previous = self.current_target_idx
                self.current_target_idx = min_idx
                self.logger.info("Monitor: server loads=%s, selected idx=%d (prev=%d)",
                                 [round(x,2) if x<1e17 else 'NA' for x in numeric_loads],
                                 self.current_target_idx, previous)

            
            hub.sleep(MONITOR_INTERVAL)

    def _request_port_stats(self, datapath):
        """Send OFPPortStatsRequest to datapath."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        """Handle replies and compute bytes/sec per port by comparing to last sample."""
        msg = ev.msg
        dpid = msg.datapath.id
        port_stats = {}
        for stat in msg.body:
            
            total_bytes = stat.tx_bytes + stat.rx_bytes
            port_stats[stat.port_no] = total_bytes

        
        last = self.last_port_bytes.setdefault(dpid, {})
        loads = self.port_load.setdefault(dpid, {})

       
        denom = max(MONITOR_INTERVAL, 0.1)

        for port_no, total_bytes in port_stats.items():
            prev = last.get(port_no, None)
            if prev is None:
                
                loads[port_no] = 0.0
            else:
                delta = total_bytes - prev
                if delta < 0:
                    
                    loads[port_no] = 0.0
                else:
                    loads[port_no] = float(delta) / denom
            
            last[port_no] = total_bytes

        
        self.port_load[dpid] = loads
        
        self.logger.debug("Port loads for dpid %s: %s", dpid, loads)