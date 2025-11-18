from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ipv4, ethernet, arp, tcp
from ryu.controller.handler import set_ev_cls
from ryu.topology import event

class LeastLoadFailover(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    VIP = "10.0.0.100"
    VIP_MAC = "AA:BB:CC:DD:EE:FF"

    SERVERS = {
        "10.0.0.2": {"port": 2, "mac": "00:00:00:00:00:02", "alive": True},
        "10.0.0.3": {"port": 3, "mac": "00:00:00:00:00:03", "alive": True},
        "10.0.0.4": {"port": 4, "mac": "00:00:00:00:00:04", "alive": True},
        "10.0.0.5": {"port": 5, "mac": "00:00:00:00:00:05", "alive": True},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.loads = {ip: 0 for ip in self.SERVERS}

    # ----------- SELECT SERVER ------------
    def select_server(self):
        alive = [ip for ip, s in self.SERVERS.items() if s["alive"]]
        return min(alive, key=lambda ip: self.loads[ip])

    # ----------- FAILOVER EVENT ------------
    @set_ev_cls(event.EventPortModify)
    def port_status(self, ev):
        port = ev.port.port_no
        alive = ev.port.is_live()

        for ip, s in self.SERVERS.items():
            if s["port"] == port:
                s["alive"] = alive
                self.logger.info(f"Server {ip} status changed: {'UP' if alive else 'DOWN'}")

    # -------- SW FEATURES --------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):

        dp = ev.msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # ARP to VIP
        match = parser.OFPMatch(eth_type=0x0806, arp_tpa=self.VIP)
        dp.send_msg(parser.OFPFlowMod(dp, priority=50, match=match,
                                      instructions=[parser.OFPInstructionActions(
                                          ofp.OFPIT_APPLY_ACTIONS,
                                          [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)])]))

    # ---------------- PACKET-IN -----------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # ARP
        if arp_pkt and arp_pkt.dst_ip == self.VIP:
            self.reply_arp(dp, eth, arp_pkt, msg.match['in_port'])
            return

        # TCP
        ip = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        if not ip or not tcp_pkt:
            return

        # CLIENT → VIP
        if ip.dst == self.VIP:

            srv = self.select_server()
            s = self.SERVERS[srv]
            self.loads[srv] += 1

            actions = [
                parser.OFPActionSetField(ipv4_dst=srv),
                parser.OFPActionSetField(eth_dst=s["mac"]),
                parser.OFPActionOutput(s["port"])
            ]
            dp.send_msg(parser.OFPPacketOut(dp,
                                            ofp.OFP_NO_BUFFER,
                                            msg.match["in_port"],
                                            actions,
                                            msg.data))

        # SERVER → CLIENT
        else:
            actions = [
                parser.OFPActionSetField(ipv4_src=self.VIP),
                parser.OFPActionSetField(eth_src=self.VIP_MAC),
                parser.OFPActionOutput(1)
            ]
            dp.send_msg(parser.OFPPacketOut(dp,
                                            ofp.OFP_NO_BUFFER,
                                            msg.match["in_port"],
                                            actions,
                                            msg.data))

    def reply_arp(self, dp, eth, arp_pkt, port):
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        reply = packet.Packet()
        reply.add_protocol(ethernet.ethernet(dst=eth.src,
                                             src=self.VIP_MAC,
                                             ethertype=0x0806))

        reply.add_protocol(arp.arp(opcode=2,
                                   src_mac=self.VIP_MAC,
                                   src_ip=self.VIP,
                                   dst_mac=arp_pkt.src_mac,
                                   dst_ip=arp_pkt.src_ip))
        reply.serialize()

        dp.send_msg(parser.OFPPacketOut(dp, ofp.OFP_NO_BUFFER,
                                        ofp.OFPP_CONTROLLER,
                                        [parser.OFPActionOutput(port)],
                                        reply.data))
