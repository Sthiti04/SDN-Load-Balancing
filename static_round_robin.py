"""
STATIC ROUND-ROBIN LOAD BALANCER WITH FAILOVER
-----------------------------------------------
This Ryu controller implements:

- Round robin scheduling (controller-driven)
- VIP → Real Server NAT
- Reverse NAT
- FF group tables (per server) for fast failover
- ARP responder for VIP
- No hashing, no dynamic load watching
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, tcp


class StaticRoundRobin(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    # -------- CONFIG --------
    VIP      = "10.0.0.100"
    VIP_MAC  = "AA:BB:CC:DD:EE:FF"
    CLIENT_PORT = 1

    SERVERS = [
        {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
        {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
        {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
        {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5},
    ]

    # Round robin pointer
    rr_index = 0

    # Server failover group mapping
    ff_group = {}

    # ----------------------------------------------------
    # SWITCH FEATURES → Install FF groups + ARP handling
    # ----------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):

        self.dp = ev.msg.datapath
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        self.logger.info("Installing STATIC ROUND ROBIN LB with FAST FAILOVER")

        # ------------- 1. ARP for VIP ---------------
        match = parser.OFPMatch(eth_type=0x806, arp_tpa=self.VIP)
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=200, match=match,
            instructions=[parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)])]
        ))

        # ------------- 2. Install FF Groups ----------
        gid = 100
        for srv in self.SERVERS:

            # primary output bucket
            p_bucket = parser.OFPBucket(
                watch_port=srv["port"],
                actions=[parser.OFPActionOutput(srv["port"])]
            )

            # fallback bucket: send to controller for rerouting
            b_bucket = parser.OFPBucket(
                watch_port=ofp.OFPP_CONTROLLER,
                actions=[parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
            )

            dp.send_msg(parser.OFPGroupMod(
                dp, ofp.OFPGC_ADD, ofp.OFPGT_FF, gid,
                [p_bucket, b_bucket]
            ))

            self.ff_group[srv["ip"]] = gid
            gid += 1

        # No forwarding flow here — RR done via controller in packet-in

    # ----------------------------------------------------
    # PACKET-IN HANDLING (RR scheduling)
    # ----------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # ------------- ARP ---------------
        if arp_pkt and arp_pkt.dst_ip == self.VIP:
            self.reply_arp(dp, eth, arp_pkt, msg.match["in_port"])
            return

        ip = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        if not ip or not tcp_pkt:
            return

        # ---------- REQUEST PATH: VIP → SERVER ----------
        if ip.dst == self.VIP:

            # Pick next server using RR pointer
            server = self.SERVERS[self.rr_index]
            self.rr_index = (self.rr_index + 1) % len(self.SERVERS)

            self.logger.info(f"RR picked server {server['ip']}")

            # NAT translation + FF group for reliability
            actions = [
                parser.OFPActionSetField(ipv4_dst=server["ip"]),
                parser.OFPActionSetField(eth_dst=server["mac"]),
                parser.OFPActionGroup(self.ff_group[server["ip"]])
            ]

            dp.send_msg(parser.OFPPacketOut(
                dp, ofp.OFP_NO_BUFFER,
                msg.match["in_port"], actions, msg.data
            ))

            return

        # ---------- RESPONSE PATH: SERVER → CLIENT ----------
        for srv in self.SERVERS:
            if ip.src == srv["ip"]:

                actions = [
                    parser.OFPActionSetField(ipv4_src=self.VIP),
                    parser.OFPActionSetField(eth_src=self.VIP_MAC),
                    parser.OFPActionOutput(self.CLIENT_PORT)
                ]

                dp.send_msg(parser.OFPPacketOut(
                    dp, ofp.OFP_NO_BUFFER,
                    msg.match["in_port"], actions, msg.data
                ))

                return

    # ----------------------------------------------------
    # VIP ARP REPLY
    # ----------------------------------------------------
    def reply_arp(self, dp, eth, a, port):

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            dst=eth.src, src=self.VIP_MAC, ethertype=0x0806))
        pkt.add_protocol(arp.arp(
            opcode=2, src_mac=self.VIP_MAC, src_ip=self.VIP,
            dst_mac=a.src_mac, dst_ip=a.src_ip))
        pkt.serialize()

        dp.send_msg(parser.OFPPacketOut(
            dp, ofp.OFP_NO_BUFFER,
            ofp.OFPP_CONTROLLER,
            [parser.OFPActionOutput(port)],
            pkt.data
        ))
