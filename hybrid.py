"""
Hybrid Load Balancing with Failover (Paper-Accurate Version)
-------------------------------------------------------------
Static Method  = SELECT GROUP + Fast Failover (Section 4.2)
Dynamic Method = Improved DWRS + Binary Search (Section 4.3)
Switching Rule = Load Imbalance δ = Variance(loads) (Section 4.4)

- When δ < threshold  → STATIC mode
- When δ ≥ threshold → DYNAMIC mode

Implements Algorithm-1:
Binary Search on cumulative serviceability list s[1..n]
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4, tcp
from ryu.topology import event
import statistics, random


class HybridDWRS_Binary(app_manager.RyuApp):
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]

    # -----------------------------------------------------
    # CONFIG
    # -----------------------------------------------------
    VIP = "10.0.0.100"
    VIP_MAC = "AA:BB:CC:DD:EE:FF"
    THRESHOLD = 15  # δ threshold for switching

    SERVERS = [
        {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
        {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
        {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
        {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5},
    ]

    MODE_STATIC = 0
    MODE_DYNAMIC = 1

    # -----------------------------------------------------
    # INIT
    # -----------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(HybridDWRS_Binary, self).__init__(*args, **kwargs)

        self.mode = self.MODE_STATIC
        self.dp = None

        # for DWRS
        self.loads = {s["ip"]: 1 for s in self.SERVERS}
        self.cumulative = []  # s[1..n] list from paper
        self.total_serviceability = 0

        self.server_ips = [s["ip"] for s in self.SERVERS]
        self.ff_group = {}  # failover group table per server

        self.update_cumulative_list()

    # -----------------------------------------------------
    # SERVICEABILITY + CUMULATIVE LIST (From Paper Section 4.3)
    # -----------------------------------------------------
    def update_cumulative_list(self):
        """
        serviceability = 1 / load
        s[i] = cumulative sum list (Algorithm-1)
        """
        running = 0
        self.cumulative = []

        for s in self.SERVERS:
            ip = s["ip"]
            serviceability = max(1, int(10 / self.loads[ip]))
            running += serviceability
            self.cumulative.append(running)

        self.total_serviceability = running

    # -----------------------------------------------------
    # Algorithm-1: Binary Search in DWRS
    # -----------------------------------------------------
    def dwrs_binary_search(self):
        """
        Implements EXACT pseudo-code:

        lw=1; up=n;
        while lw+1<up:
            mid=(lw+up)/2
            if r <= s[mid] then up=mid else lw=mid
        ts=up
        """
        r = random.randint(1, self.total_serviceability)

        lw = 0
        up = len(self.cumulative) - 1

        while lw + 1 < up:
            mid = (lw + up) // 2
            if r <= self.cumulative[mid]:
                up = mid
            else:
                lw = mid

        return up  # index of selected server

    # -----------------------------------------------------
    # SWITCHING LOGIC — δ = Variance(loads)
    # -----------------------------------------------------
    def compute_delta(self):
        return statistics.pvariance(list(self.loads.values()))

    def update_mode(self):
        δ = self.compute_delta()

        if self.mode == self.MODE_STATIC and δ >= self.THRESHOLD:
            self.logger.info(f"δ={δ} / Switching STATIC → DYNAMIC")
            self.install_dynamic_mode()

        elif self.mode == self.MODE_DYNAMIC and δ < self.THRESHOLD:
            self.logger.info(f"δ={δ} / Switching DYNAMIC → STATIC")
            self.install_static_mode()

    # -----------------------------------------------------
    # STATIC MODE = SELECT GROUP + FF (Paper Section 4.2)
    # -----------------------------------------------------
    def install_static_mode(self):
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # delete dynamic flows (paper requirement)
        self.delete_dynamic_flows()

        # ---------- Build FF Groups ----------
        gid = 200
        self.ff_group = {}

        for s in self.SERVERS:

            b1 = parser.OFPBucket(
                watch_port=s["port"],
                actions=[parser.OFPActionOutput(s["port"])]
            )
            b2 = parser.OFPBucket(
                watch_port=ofp.OFPP_CONTROLLER,
                actions=[parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
            )

            dp.send_msg(parser.OFPGroupMod(
                dp, ofp.OFPGC_ADD, ofp.OFPGT_FF, gid, [b1, b2]
            ))

            self.ff_group[s["ip"]] = gid
            gid += 1

        # ---------- SELECT Group ----------
        buckets = []
        for s in self.SERVERS:
            actions = [
                parser.OFPActionSetField(ipv4_dst=s["ip"]),
                parser.OFPActionSetField(eth_dst=s["mac"]),
                parser.OFPActionGroup(self.ff_group[s["ip"]])
            ]
            buckets.append(parser.OFPBucket(actions=actions))

        dp.send_msg(parser.OFPGroupMod(
            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT, 50, buckets
        ))

        # Forward VIP → SELECT group
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=self.VIP)
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=30, match=match,
            instructions=[parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [parser.OFPActionGroup(50)])]
        ))

        # Reverse NAT
        for s in self.SERVERS:
            match = parser.OFPMatch(eth_type=0x0800, ipv4_src=s["ip"])
            acts = [
                parser.OFPActionSetField(ipv4_src=self.VIP),
                parser.OFPActionSetField(eth_src=self.VIP_MAC),
                parser.OFPActionOutput(1)
            ]
            dp.send_msg(parser.OFPFlowMod(
                dp, priority=30, match=match,
                instructions=[parser.OFPInstructionActions(
                    ofp.OFPIT_APPLY_ACTIONS, acts)]
            ))

        self.mode = self.MODE_STATIC

    # -----------------------------------------------------
    # DELETE STATIC MODE (Paper Section 4.4)
    # -----------------------------------------------------
    def delete_static_mode(self):
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # Delete SELECT
        dp.send_msg(parser.OFPGroupMod(dp, ofp.OFPGC_DELETE,
                                       ofp.OFPGT_SELECT, 50))

        # Delete VIP→server flows
        dp.send_msg(parser.OFPFlowMod(
            dp, command=ofp.OFPFC_DELETE,
            match=parser.OFPMatch(ipv4_dst=self.VIP)
        ))

    # -----------------------------------------------------
    # INSTALL DYNAMIC MODE (DWRS)
    # -----------------------------------------------------
    def install_dynamic_mode(self):

        # remove static first (paper requirement)
        self.delete_static_mode()

        # DWRS operates ONLY through packet-in → no static flows
        self.mode = self.MODE_DYNAMIC

    # -----------------------------------------------------
    # DELETE dynamic flows
    # -----------------------------------------------------
    def delete_dynamic_flows(self):
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        dp.send_msg(parser.OFPFlowMod(
            dp, command=ofp.OFPFC_DELETE,
            match=parser.OFPMatch(ipv4_dst=self.VIP)
        ))

    # -----------------------------------------------------
    # SWITCH FEATURES HANDLER
    # -----------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        self.dp = ev.msg.datapath
        dp = self.dp
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        # intercept ARP
        match = parser.OFPMatch(eth_type=0x0806, arp_tpa=self.VIP)
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=100, match=match,
            instructions=[parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                [parser.OFPActionOutput(ofp.OFPP_CONTROLLER)])]
        ))

        self.install_static_mode()

    # -----------------------------------------------------
    # PACKET-IN = only used in DYNAMIC mode
    # -----------------------------------------------------
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packetin(self, ev):

        msg = ev.msg
        dp = msg.datapath
        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        arp_pkt = pkt.get_protocol(arp.arp)

        # ARP reply
        if arp_pkt and arp_pkt.dst_ip == self.VIP:
            self.reply_arp(dp, eth, arp_pkt, msg.match["in_port"])
            return

        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt = pkt.get_protocol(tcp.tcp)
        if not ipv4_pkt or not tcp_pkt:
            return

        # STATIC = hardware does everything
        if self.mode == self.MODE_STATIC:
            return

        # --------------------------
        # DYNAMIC (DWRS Selection)
        # --------------------------
        self.update_mode()
        self.update_cumulative_list()

        idx = self.dwrs_binary_search()
        target = self.SERVERS[idx]
        ip = target["ip"]

        self.loads[ip] += 1  # update load counters

        actions = [
            parser.OFPActionSetField(ipv4_dst=ip),
            parser.OFPActionSetField(eth_dst=target["mac"]),
            parser.OFPActionGroup(self.ff_group[ip])
        ]

        dp.send_msg(parser.OFPPacketOut(
            dp, ofp.OFP_NO_BUFFER,
            msg.match["in_port"], actions, msg.data
        ))

    # -----------------------------------------------------
    # ARP
    # -----------------------------------------------------
    def reply_arp(self, dp, eth, arp_pkt, port):

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(
            dst=eth.src, src=self.VIP_MAC, ethertype=0x0806))
        pkt.add_protocol(arp.arp(
            opcode=2, src_mac=self.VIP_MAC, src_ip=self.VIP,
            dst_mac=arp_pkt.src_mac, dst_ip=arp_pkt.src_ip))

        pkt.serialize()

        dp.send_msg(parser.OFPPacketOut(
            dp, ofp.OFP_NO_BUFFER,
            ofp.OFPP_CONTROLLER,
            [parser.OFPActionOutput(port)], pkt.data
        ))
