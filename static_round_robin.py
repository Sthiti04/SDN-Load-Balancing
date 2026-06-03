from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, arp, ipv4
from ryu.lib.packet import ether_types

class StaticRRLoadBalancer(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # VIP for load balancing
        self.vip_ip = "10.0.0.100"
        self.vip_mac = "00:00:00:00:00:FE"

        # Server ports (h2-h5)
        self.server_ports = [2, 3, 4, 5]

        # Round-robin index
        self.rr_index = 0

        # MAC learning table: {dpid: {mac: port}}
        self.mac_to_port = {}

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofp.OFPP_CONTROLLER,
                                          ofp.OFPCML_NO_BUFFER)]
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath,
                                priority=0,
                                match=match,
                                instructions=inst)
        datapath.send_msg(mod)

        self.logger.info("Switch table-miss flow installed")

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        # Ignore LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})

        # Learn MAC of the source
        self.mac_to_port[dpid][eth.src] = in_port

        # Handle ARP
        arp_pkt = pkt.get_protocol(arp.arp)
        if arp_pkt:
            self.handle_arp(datapath, in_port, eth, arp_pkt, msg)
            return

        # Handle IPv4 traffic to VIP (round-robin)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        if ip_pkt and ip_pkt.dst == self.vip_ip and in_port == 1:  # client port
            self.handle_rr(datapath, msg)
            return

        # Normal L2 switching for all other traffic
        out_port = self.mac_to_port[dpid].get(eth.dst, ofp.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=in_port,
                                  actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)

    def handle_arp(self, datapath, in_port, eth, arp_pkt, msg):
        parser = datapath.ofproto_parser
        ofp = datapath.ofproto

        # ARP request for VIP
        if arp_pkt.opcode == arp.ARP_REQUEST and arp_pkt.dst_ip == self.vip_ip:
            reply = packet.Packet()
            reply.add_protocol(
                ethernet.ethernet(
                    src=self.vip_mac,
                    dst=eth.src,
                    ethertype=ether_types.ETH_TYPE_ARP
                )
            )
            reply.add_protocol(
                arp.arp(
                    opcode=arp.ARP_REPLY,
                    src_mac=self.vip_mac,
                    src_ip=self.vip_ip,
                    dst_mac=eth.src,
                    dst_ip=arp_pkt.src_ip
                )
            )
            reply.serialize()
            actions = [parser.OFPActionOutput(in_port)]
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofp.OFP_NO_BUFFER,
                                      in_port=ofp.OFPP_CONTROLLER,
                                      actions=actions,
                                      data=reply.data)
            datapath.send_msg(out)
        else:
            # Flood other ARP packets
            out_port = ofp.OFPP_FLOOD
            actions = [parser.OFPActionOutput(out_port)]
            out = parser.OFPPacketOut(datapath=datapath,
                                      buffer_id=ofp.OFP_NO_BUFFER,
                                      in_port=in_port,
                                      actions=actions,
                                      data=msg.data)
            datapath.send_msg(out)

    def handle_rr(self, datapath, msg):
        parser = datapath.ofproto_parser
        ofp = datapath.ofproto

        # Pick next server in round robin
        server_port = self.server_ports[self.rr_index]
        self.rr_index = (self.rr_index + 1) % len(self.server_ports)

        # Forward the packet to the selected server
        actions = [parser.OFPActionOutput(server_port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=msg.buffer_id,
                                  in_port=msg.match['in_port'],
                                  actions=actions,
                                  data=msg.data)
        datapath.send_msg(out)