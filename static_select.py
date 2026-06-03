from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, arp


SERVERS = [
    {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
    {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
    {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
    {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5}
]

VIP = "10.0.0.100"   # Virtual IP
CLIENT_PORT = 1      # h1 is client connected on port 1
GROUP_ID = 50        # arbitrary ID for SELECT group

class StaticSelectLB(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(StaticSelectLB, self).__init__(*args, **kwargs)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.install_default_flows(datapath)
        self.install_select_group(datapath)
        self.install_vip_flow(datapath)

    def install_default_flows(self, datapath):
        """Install default flows for ARP + normal IP forwarding"""
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        # Allow ARP flooding
        match = parser.OFPMatch(eth_type=0x0806)
        actions = [parser.OFPActionOutput(ofp.OFPP_FLOOD)]
        self.add_flow(datapath, 1, match, actions)

        # Normal IP forwarding (for pingall etc.)
        match = parser.OFPMatch(eth_type=0x0800)
        actions = [parser.OFPActionOutput(ofp.OFPP_NORMAL)]
        self.add_flow(datapath, 1, match, actions)

    def install_select_group(self, datapath):
        """Create a SELECT group with all servers"""
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        buckets = []

        for srv in SERVERS:
            actions = [
                parser.OFPActionSetField(ipv4_dst=srv['ip']),
                parser.OFPActionSetField(eth_dst=srv['mac']),
                parser.OFPActionOutput(srv['port'])
            ]
            bucket = parser.OFPBucket(actions=actions, watch_port=srv['port'])
            buckets.append(bucket)

        req = parser.OFPGroupMod(datapath,
                                 ofp.OFPGC_ADD,
                                 ofp.OFPGT_SELECT,
                                 GROUP_ID,
                                 buckets)
        datapath.send_msg(req)
        self.logger.info("Installed SELECT group with %d servers", len(SERVERS))

    def install_vip_flow(self, datapath):
        """Send VIP traffic to the SELECT group"""
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=VIP)
        actions = [parser.OFPActionGroup(GROUP_ID)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]

        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=100,
                                match=match,
                                instructions=inst)
        datapath.send_msg(mod)
        self.logger.info("Installed VIP flow for %s", VIP)

    def add_flow(self, datapath, priority, match, actions):
        """Helper to install flows"""
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=priority,
                                match=match,
                                instructions=inst)
        datapath.send_msg(mod)