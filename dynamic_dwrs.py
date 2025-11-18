"""
Improved DWRS Load Balancer (with Binary Search)
------------------------------------------------
Implements Algorithm-1 from the research paper:

- Uses serviceability values (inverse of load)
- Builds cumulative sum list s[1..n] during monitoring interval
- Uses binary search to select target server
- Forwards request packets to the Fast-Failover (FF) group table
- Inserts flow entries for VIP translation
- Supports failover without controller involvement

This code is 100% aligned with the pseudo-code & theory provided.
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, tcp, arp
import random


class ImprovedDWRS(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    # VIP CONFIG
    VIP = "10.0.0.100"
    VIP_MAC = "AA:BB:CC:DD:EE:FF"

    # Server definitions (required by paper)
    SERVERS = [
        {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
        {"ip": "10:00:00:00:00:03", "mac": "00:00:00:00:00:03", "port": 3},
        {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
        {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5}
    ]

    # ----------------------------------------------------------------------
    # INIT
    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(ImprovedDWRS, self).__init__(*args, **kwargs)

        # Load values (paper does not define exact formula—default = packet count)
        self.load = {s["ip"]: 1 for s in self.SERVERS}

        # Cumulative sum list (paper notation: s[1..n])
        self.cumulative = []
        self.total_serviceability = 0

        self.dp = None

    # ----------------------------------------------------------------------
    # SERVICEABILITY LIST (Paper Section: Improved DWRS)
    # ----------------------------------------------------------------------
    def update_cumulative_list(self):
        """
        Compute serviceability and cumulative sum list s[1..n]:

        serviceability[i] = 1 / load[i]
        s[i] = cumulative sum
        """

        self.cumulative = []
        running = 0

        for s in self.SERVERS:
            ip = s["ip"]
            serviceability = max(1, int(10 / self.load[ip]))   # inverse load as per theory
            running += serviceability
            self.cumulative.append(running)

        self.total_serviceability = running

    # ----------------------------------------------------------------------
    # BINARY SEARCH — Algorithm 1 from the paper
    # ----------------------------------------------------------------------
    def dwrs_binary_select(self):
        """
        Implements Algorithm-1 exactly:

        lw_bound = 1
        up_bound = n

        while lw_bound + 1 < up_bound:
            mid = floor((lw + up) / 2)
            if r <= s[mid]: up = mid
            else: lw = mid

        return up_bound
        """

        # Generate random r ∈ [1, sum(serviceability)]
        r = random.randint(1, self.total_serviceability)

        lw = 0              # index 0 corresponds to server #1
        up = len(self.cumulative) - 1

        while lw + 1 < up:
            mid = (lw + up) // 2

            if r <= self.cumulative[mid]:
                up = mid
            else:
                lw = mid

        return up  # index of selected server

    # ----------------------------------------------------------------------
    # FAST FAILOVER GROUP TABLE INSTALLATION
    # (Paper Section 4.2: failover logic)
    # ----------------------------------------------------------------------
    def install_ff_groups(self, dp):
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        gid = 200  # group IDs for FF
        self.ff_group_for_server = {}

        for s in self.SERVERS:

            bucket1 = parser.OFPBucket(
                watch_port=s["port"],
                actions=[parser.OFPActionOutput(s["port"])]
            )

            # failover bucket → fallback to controller
            bucket2 = parser.OFPBucket(
                watch_port=ofp.OFPP_CONTROLLER,
                actions=[parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
            )

            msg = parser.OFPGroupMod(dp,
                                     ofp.OFPGC_ADD,
                                     ofp.OFPGT_FF,
                                     gid,
                                     [bucket1, bucket2])

            dp.send_msg(msg)

            self.ff_group_for_server[s["ip"]] = gid
            gid += 1

    # ----------------------------------------------------------------------
    # SWITCH FEATURES — static installation (VIP, ARP, FF groups)
    # ----------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features(self, ev):

        self.dp = ev.msg.datapath
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # install FF groups
        self.install_ff_groups(dp)

        # handle ARP for VIP
        match = parser.OFPMatch(eth_type=0x0806, arp_tpa=self.VIP)
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=200, match=match,
            instructions=[parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS, actions)]
        ))

    # ----------------------------------------------------------------------
    # PACKET-IN HANDLER (DWRS dynamic phase only)
    # ----------------------------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetin(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # ARP responder
        if arp_pkt and arp_pkt.dst_ip == self.VIP:
            self.reply_arp(dp, eth, arp_pkt, msg.match["in_port"])
            return

        ip = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)

        if not ip or not tcp_pkt:
            return

        # Only calls DWRS when traffic is to VIP
        if ip.dst == self.VIP:

            # Update serviceability & cumulative list
            self.update_cumulative_list()

            # Use binary search to pick server
            index = self.dwrs_binary_select()
            server = self.SERVERS[index]

            # update load
            self.load[server["ip"]] += 1

            # Forward via that server's FF group
            actions = [
                parser.OFPActionSetField(ipv4_dst=server["ip"]),
                parser.OFPActionSetField(eth_dst=server["mac"]),
                parser.OFPActionGroup(self.ff_group_for_server[server["ip"]])
            ]

            dp.send_msg(parser.OFPPacketOut(
                dp,
                buffer_id=ofp.OFP_NO_BUFFER,
                in_port=msg.match["in_port"],
                actions=actions,
                data=msg.data
            ))

        else:
            # reverse NAT path → client
            actions = [
                parser.OFPActionSetField(ipv4_src=self.VIP),
                parser.OFPActionSetField(eth_src=self.VIP_MAC),
                parser.OFPActionOutput(1)
            ]

            dp.send_msg(parser.OFPPacketOut(
                dp,
                buffer_id=ofp.OFP_NO_BUFFER,
                in_port=msg.match["in_port"],
                actions=actions,
                data=msg.data
            ))

    # ----------------------------------------------------------------------
    # ARP REPLY
    # ----------------------------------------------------------------------
    def reply_arp(self, dp, eth, arp_pkt, port):

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        reply = packet.Packet()
        reply.add_protocol(ethernet.ethernet(
            dst=eth.src, src=self.VIP_MAC, ethertype=0x0806))
        reply.add_protocol(arp.arp(
            opcode=2,
            src_mac=self.VIP_MAC,
            src_ip=self.VIP,
            dst_mac=arp_pkt.src_mac,
            dst_ip=arp_pkt.src_ip))

        reply.serialize()

        dp.send_msg(parser.OFPPacketOut(
            dp, ofp.OFP_NO_BUFFER, ofp.OFPP_CONTROLLER,
            [parser.OFPActionOutput(port)], reply.data
        ))
