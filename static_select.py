"""
STATIC METHOD LOAD BALANCER WITH FAILOVER
------------------------------------------
Implements Section 4.2 of the research paper exactly.

- Uses SELECT group table with one bucket per server
- Hash-based selection ensures same client → same server
- watch_port removes dead servers automatically
- Flow for VIP → SELECT group
- Flow for server → client (NAT return)
- ARP handler for VIP
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, tcp


class StaticSelectLB(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    # ----------------- CONFIG -----------------
    VIP = "10.0.0.100"
    VIP_MAC = "AA:BB:CC:DD:EE:FF"
    CLIENT_PORT = 1

    SERVERS = [
        {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
        {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
        {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
        {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5},
    ]

    GROUP_ID = 50  # SELECT group ID

    # --------------------------------------------------------
    # Switch Features → Install STATIC LB
    # --------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):

        self.dp = ev.msg.datapath
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        self.logger.info("Installing STATIC SELECT LB with hash-based selection + failover")

        # -----------------------------
        # 1. ARP for VIP → Controller
        # -----------------------------
        match = parser.OFPMatch(eth_type=0x0806, arp_tpa=self.VIP)
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=200, match=match,
            instructions=[parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)])]
        ))

        # -----------------------------
        # 2. Build SELECT GROUP TABLE
        # -----------------------------
        buckets = []

        for s in self.SERVERS:

            actions = [
                # NAT translation (VIP → server IP)
                parser.OFPActionSetField(ipv4_dst=s["ip"]),
                parser.OFPActionSetField(eth_dst=s["mac"]),

                # send to server port
                parser.OFPActionOutput(s["port"])
            ]

            bucket = parser.OFPBucket(
                actions=actions,
                watch_port=s["port"],          # failover on port down
                watch_group=ofp.OFPG_ANY
            )

            buckets.append(bucket)

        # Install SELECT group with hash-based selection
        dp.send_msg(parser.OFPGroupMod(
            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT,
            self.GROUP_ID, buckets
        ))

        # -----------------------------
        # 3. VIP → SELECT group flow
        # -----------------------------
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=self.VIP)
        inst = [parser.OFPInstructionActions(
            ofp.OFPIT_APPLY_ACTIONS,
            [parser.OFPActionGroup(self.GROUP_ID)])]

        dp.send_msg(parser.OFPFlowMod(
            dp, priority=100, match=match, instructions=inst
        ))

        # -----------------------------
        # 4. Server → Client NAT return
        # -----------------------------
        for s in self.SERVERS:

            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=s["ip"])

            actions = [
                parser.OFPActionSetField(ipv4_src=self.VIP),
                parser.OFPActionSetField(eth_src=self.VIP_MAC),
                parser.OFPActionOutput(self.CLIENT_PORT)
            ]

            dp.send_msg(parser.OFPFlowMod(
                dp, priority=100, match=match,
                instructions=[parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, actions)]
            ))

    # --------------------------------------------------------
    # PACKET-IN → Only ARP Replies Required
    # --------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetin(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # ARP reply for VIP
        if arp_pkt and arp_pkt.dst_ip == self.VIP:
            self.reply_arp(dp, eth, arp_pkt, msg.match["in_port"])
            return

    # --------------------------------------------------------
    # ARP REPLY FOR VIP
    # --------------------------------------------------------
    def reply_arp(self, dp, eth, arp_pkt, port):

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        rp = packet.Packet()
        rp.add_protocol(ethernet.ethernet(
            dst=eth.src,
            src=self.VIP_MAC,
            ethertype=0x0806))
        rp.add_protocol(arp.arp(
            opcode=2,
            src_mac=self.VIP_MAC,
            src_ip=self.VIP,
            dst_mac=arp_pkt.src_mac,
            dst_ip=arp_pkt.src_ip))
        rp.serialize()

        dp.send_msg(parser.OFPPacketOut(
            dp, ofp.OFP_NO_BUFFER,
            ofp.OFPP_CONTROLLER,
            [parser.OFPActionOutput(port)],
            rp.data
        ))
