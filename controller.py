# integrated_controller_annotated.py

# Import Ryu app base so we can create a Ryu application class
from ryu.base import app_manager

# OpenFlow protocol events (packet in, stats reply, switch features, etc.)
from ryu.controller import ofp_event

# Dispatcher constants and decorator to register event handlers
from ryu.controller.handler import MAIN_DISPATCHER, CONFIG_DISPATCHER, set_ev_cls

# OpenFlow 1.3 definitions (messages, constants, parser)
from ryu.ofproto import ofproto_v1_3

# Packet parsing helpers: generic packet container and protocol classes
from ryu.lib.packet import packet, ethernet, arp, ipv4, icmp, ether_types

# Hub provides a cooperative threading model used for the monitor thread
from ryu.lib import hub

# To detect when a datapath goes away
from ryu.controller.handler import DEAD_DISPATCHER

# Standard time module (not heavily used here but often useful)
import time


# Define our Ryu application class inheriting from RyuApp
class IntegratedController(app_manager.RyuApp):
    # Specify the OpenFlow versions this app supports (here: OF 1.3)
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # How often (seconds) the controller polls switches for port stats
    MONITOR_INTERVAL = 5   # seconds

    # Example threshold (bytes per MONITOR_INTERVAL) to trigger reroute logic
    THROUGHPUT_THRESHOLD = 1000000  # bytes per MONITOR_INTERVAL

    # Constructor: called when the Ryu app starts
    def __init__(self, *args, **kwargs):
        # Call the parent constructor (important Ryu initialisation)
        super(IntegratedController, self).__init__(*args, **kwargs)

        # Mapping: datapath id (dpid) -> { mac_address: port_no }
        # used for basic L2 learning per-switch
        self.mac_to_port = {}

        # Mapping: ip_address -> (dpid, port_no, mac) — where that IP was last seen
        # used for simple IP->location resolution (helps with L3 decisions & ARP replies)
        self.ip_to_location = {}

        # Track active datapaths (connected switches) as { dpid: datapath_object }
        self.datapaths = {}

        # Store previous port tx byte counters for throughput calculation:
        # { dpid: { port_no: previous_tx_bytes } }
        self.prev_port_bytes = {}

        # Start a background (green) thread that periodically requests port stats
        # hub.spawn returns immediately and runs _monitor concurrently
        self.monitor_thread = hub.spawn(self._monitor)


    # ---- Datapath lifecycle handlers ----
    # Handle datapath state changes (connect/disconnect)
    @set_ev_cls(ofp_event.EventOFPStateChange)
    def _state_change_handler(self, ev):
        # ev.datapath is the switch object that changed state
        dp = ev.datapath

        # If datapath reached MAIN_DISPATCHER, it's fully connected and ready
        if ev.state == MAIN_DISPATCHER:
            # Log the registration
            self.logger.info("Registering datapath: %s", dp.id)
            # Save the datapath object for later use (stats requests, flow mods)
            self.datapaths[dp.id] = dp
            # Ensure there is an entry for prev_port_bytes for this dpid
            self.prev_port_bytes.setdefault(dp.id, {})

        # If datapath transitioned to DEAD_DISPATCHER, it has disconnected
        elif ev.state == DEAD_DISPATCHER:
            # Remove the datapath from our tracking structures if present
            if dp.id in self.datapaths:
                self.logger.info("Unregistering datapath: %s", dp.id)
                del self.datapaths[dp.id]
                del self.prev_port_bytes[dp.id]


    # ---- Switch features handler: install table-miss flow ----
    # Called when a switch first connects and sends its features message
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        # Extract commonly used objects from the event
        datapath = ev.msg.datapath                # the switch object
        ofproto = datapath.ofproto                # OF protocol constants
        parser = datapath.ofproto_parser          # message builder/parser

        # Build a match that matches all packets (empty match == table-miss)
        match = parser.OFPMatch()

        # Build an action to send matching packets to the controller
        # OFPP_CONTROLLER: send to controller; OFPCML_NO_BUFFER: include full packet
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]

        # Wrap actions in an instruction to apply them
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        # Create a FlowMod message installing the table-miss (priority 0)
        mod = parser.OFPFlowMod(datapath=datapath, priority=0,
                                match=match, instructions=inst)

        # Send the FlowMod to the switch
        datapath.send_msg(mod)

        # Log that we installed the table-miss entry
        self.logger.info("Installed table-miss on datapath %s", datapath.id)


    # ---- Packet-in handler ----
    # Handles PacketIn events (packets sent by switches to controller)
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        # Extract the OpenFlow message and related helpers
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Which port the packet arrived on
        in_port = msg.match.get('in_port')

        # Parse the raw packet (msg.data) into a Ryu packet.Packet object
        pkt = packet.Packet(msg.data)

        # Extract the Ethernet header (if present)
        eth = pkt.get_protocol(ethernet.ethernet)

        # If there is no ethernet header, ignore (defensive)
        if eth is None:
            return

        # Ensure mac_to_port has an entry for this dpid
        self.mac_to_port.setdefault(dpid, {})

        # Learn mapping: source MAC seen on this switch is reachable via in_port
        self.mac_to_port[dpid][eth.src] = in_port  # learn mac->port on this switch

        # Try to extract ARP and IPv4 payloads (if present)
        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        # If it's an ARP packet, delegate to ARP handler
        if arp_pkt:
            self._handle_arp(datapath, in_port, eth, arp_pkt, msg.data)
            return

        # If it's an IPv4 packet, delegate to IPv4 handler
        if ip_pkt:
            self._handle_ipv4(datapath, in_port, eth, ip_pkt, msg.data)
            return


    # ---- ARP handling ----
    def _handle_arp(self, datapath, in_port, eth, arp_pkt, raw_data):
        # Extract local helpers for this datapath
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Extract ARP fields
        src_ip = arp_pkt.src_ip
        src_mac = arp_pkt.src_mac
        dst_ip = arp_pkt.dst_ip

        # Learn where the source IP is (dpid, port, mac)
        self.ip_to_location[src_ip] = (dpid, in_port, src_mac)
        self.logger.info("Learned IP %s -> (dpid=%s, port=%s, mac=%s)",
                         src_ip, dpid, in_port, src_mac)

        # If ARP request, attempt to reply if we know the target
        if arp_pkt.opcode == arp.ARP_REQUEST:
            # If we have seen the target IP before, craft and send an ARP reply
            if dst_ip in self.ip_to_location:
                # lookup the known location for dst_ip
                (dst_dpid, dst_port, dst_mac) = self.ip_to_location[dst_ip]

                # Build an ethernet frame with src = target's MAC and dst = requester's MAC
                arp_reply = packet.Packet()
                arp_reply.add_protocol(
                    ethernet.ethernet(ethertype=eth.ethertype,
                                      dst=src_mac,   # send back to requester
                                      src=dst_mac))  # impersonate the target's MAC

                # Build the ARP reply payload: opcode = ARP_REPLY
                arp_reply.add_protocol(
                    arp.arp(opcode=arp.ARP_REPLY,
                            src_mac=dst_mac,   # target's MAC
                            src_ip=dst_ip,     # target's IP
                            dst_mac=src_mac,   # requester's MAC
                            dst_ip=src_ip))    # requester's IP

                # Serialize the packet into bytes
                arp_reply.serialize()
                data = arp_reply.data

                # Send the reply out the port where the request arrived
                actions = [parser.OFPActionOutput(in_port)]
                out = parser.OFPPacketOut(datapath=datapath,
                                          buffer_id=ofproto.OFP_NO_BUFFER,
                                          in_port=ofproto.OFPP_CONTROLLER,
                                          actions=actions,
                                          data=data)
                datapath.send_msg(out)

                # Log that we sent an ARP reply
                self.logger.info("Sent ARP reply for %s to %s", dst_ip, src_ip)

            else:
                # If target unknown, flood the ARP so remote hosts/switches may answer
                self._flood(datapath, in_port, raw_data)

        # If ARP reply: learn the mapping for the sender (they told us)
        elif arp_pkt.opcode == arp.ARP_REPLY:
            self.ip_to_location[arp_pkt.src_ip] = (dpid, in_port, arp_pkt.src_mac)
            self.logger.info("Received ARP reply: learned %s -> %s", arp_pkt.src_ip, arp_pkt.src_mac)


    # ---- IPv4 handling: simple L3 (static-like forwarding) ----
    def _handle_ipv4(self, datapath, in_port, eth, ip_pkt, raw_data):
        # Basic local references
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Extract IP fields
        src_ip = ip_pkt.src
        dst_ip = ip_pkt.dst
        proto = ip_pkt.proto

        # Learn where source IP is (dpid, port, mac)
        self.ip_to_location[src_ip] = (dpid, in_port, eth.src)
        self.logger.info("Learned IP %s -> (dpid=%s, port=%s, mac=%s)",
                         src_ip, dpid, in_port, eth.src)

        # Very simple prefix check to decide which switch "owns" which subnet
        # (This is static/simple; replace with topology discovery in production)
        if dst_ip.startswith('10.0.0.'):
            target_dpid = 1
        elif dst_ip.startswith('10.0.1.'):
            target_dpid = 2
        else:
            target_dpid = None

        # If we already know exactly where the destination IP is
        if dst_ip in self.ip_to_location:
            (dst_dpid, dst_port, dst_mac) = self.ip_to_location[dst_ip]

            # If destination is on same switch, use the host port; else use inter-switch port
            if dst_dpid == dpid:
                out_port = dst_port
            else:
                # Assumes port 3 connects to the other switch in this simple topo
                out_port = 3

            # Build actions to output to the chosen port
            actions = [parser.OFPActionOutput(out_port)]
            data = raw_data

            # Send the packet out now
            self._send_packet_out(datapath, data, actions)

            # Also install a flow so future packets for this IPv4 dst bypass the controller
            match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
            inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
            mod = parser.OFPFlowMod(datapath=datapath, priority=10,
                                    match=match, instructions=inst,
                                    idle_timeout=30, hard_timeout=0)
            datapath.send_msg(mod)

            self.logger.info("Installed flow on dpid %s to reach %s via port %s", dpid, dst_ip, out_port)
            return

        # Destination unknown but we can infer which switch should reach it (target_dpid != None)
        if target_dpid is not None:
            # If this datapath *is* the target switch but we still don't know the host's port:
            if dpid == target_dpid:
                # Flood locally so the host (if present) replies and we learn its IP->port mapping
                self._flood(datapath, in_port, raw_data)
            else:
                # Otherwise forward toward the other switch (here assumed to be port 3)
                out_port = 3
                actions = [parser.OFPActionOutput(out_port)]
                self._send_packet_out(datapath, raw_data, actions)

                # Install a reactive flow that forwards future traffic for this dst out the inter-switch port
                match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
                inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
                mod = parser.OFPFlowMod(datapath=datapath, priority=5,
                                        match=match, instructions=inst,
                                        idle_timeout=20, hard_timeout=0)
                datapath.send_msg(mod)

                self.logger.info("Forwarding to inter-switch port %s on dpid %s for dst %s", out_port, dpid, dst_ip)
            return

        # If none of the above applied, as a last resort flood so the network can resolve the address
        self._flood(datapath, in_port, raw_data)


    # ---- Helpers ----
    # Generic helper to send a packet-out with given actions and raw data
    def _send_packet_out(self, datapath, data, actions):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Build a PacketOut message: send the provided 'data' from controller to switch with actions
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=data)
        datapath.send_msg(out)


    # Flood helper: send the packet to all switch ports (except the ingress)
    def _flood(self, datapath, in_port, data):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Use OFPP_FLOOD to broadcast on the switch
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions, data=data)
        datapath.send_msg(out)

        # Log flooding for debugging
        self.logger.info("Flooded packet on dpid %s in_port %s", datapath.id, in_port)


    # ---- Monitoring thread ----
    # Background loop that requests port stats from each connected datapath periodically
    def _monitor(self):
        while True:
            # Iterate a copy of datapaths (list) to avoid runtime modification issues
            for dp in list(self.datapaths.values()):
                self._request_port_stats(dp)
            # Sleep for configured interval before next round
            hub.sleep(self.MONITOR_INTERVAL)


    # Send an OFPPortStatsRequest to a switch
    def _request_port_stats(self, datapath):
        self.logger.debug("Requesting port stats from %s", datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # OFPP_ANY requests stats for all ports
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)


    # ---- Stats reply handler ----
    # Handler for port statistics replies from switches
    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        # Which datapath sent this reply
        dpid = ev.msg.datapath.id

        # Loop over each port's stats in the reply
        for stat in ev.msg.body:
            port_no = stat.port_no
            tx_bytes = stat.tx_bytes

            # Get the previous tx byte count we recorded for this port (if any)
            prev = self.prev_port_bytes.get(dpid, {}).get(port_no, None)

            # If we have a previous value, compute difference -> throughput
            if prev is not None:
                byte_diff = tx_bytes - prev
                # Throughput in bytes per second across the MONITOR_INTERVAL
                throughput = byte_diff / float(self.MONITOR_INTERVAL)
                self.logger.info("DPID %s, port %s throughput: %.2f bytes/s", dpid, port_no, throughput)

                # If throughput exceeds configured threshold trigger reroute demo
                if throughput > self.THROUGHPUT_THRESHOLD:
                    self.logger.warning("High usage on dpid %s port %s (%.2f B/s) -> consider reroute", dpid, port_no, throughput)
                    # Attempt a simple reroute demonstration
                    self._attempt_reroute(ev.msg.datapath, port_no)

            # Save this stat for next interval comparison
            self.prev_port_bytes.setdefault(dpid, {})[port_no] = tx_bytes


    # ---- Simple reroute demo ----
    def _attempt_reroute(self, datapath, congested_port):
        """
        Demo reroute: install higher priority flow matching TCP and redirect to an alternate port.
        This is a simplistic demo; in a real network you would compute alternate path via
        topology discovery and choose appropriate next-hop ports.
        """
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Demo assumption: alternate port to use is 2 (change this to match your topology)
        ALT_PORT = 2
        self.logger.info("Installing demo reroute on dpid %s: redirecting TCP flows to port %s", datapath.id, ALT_PORT)

        # Match IPv4 TCP packets (eth_type=0x0800, ip_proto=6)
        match = parser.OFPMatch(eth_type=0x0800, ip_proto=6)  # ip_proto=6 => TCP

        # Action: send matching packets out ALT_PORT
        actions = [parser.OFPActionOutput(ALT_PORT)]
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]

        # FlowMod: priority high so this rule takes precedence when active
        mod = parser.OFPFlowMod(datapath=datapath, priority=50,
                                match=match, instructions=inst,
                                idle_timeout=30, hard_timeout=0)
        datapath.send_msg(mod)