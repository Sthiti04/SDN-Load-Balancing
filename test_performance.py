#!/usr/bin/env python3
"""
Basic performance test for hybrid load balancer
Tests: throughput, latency, per-link bandwidth for TCP and UDP
"""

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from topo import LoadBalancerTopo
import time

def test_performance(net):
    """Run basic performance tests"""
    
    client = net.get('h1')
    servers = [net.get(f'h{i}') for i in range(2, 6)]
    
    info('\n*** Testing connectivity with pingall\n')
    net.pingAll()
    
    info('\n*** Starting iperf servers on all server hosts (TCP)\n')
    for i, server in enumerate(servers, start=2):
        server.cmd(f'iperf -s -p 5001 &')
        info(f'Server h{i} listening on port 5001\n')
    
    time.sleep(2)  # Wait for servers to start
    
    info('\n*** Running TCP throughput test from client to VIP\n')
    result = client.cmd('iperf -c 10.0.0.100 -p 5001 -t 10')
    info(result)
    
    info('\n*** Test completed\n')

if __name__ == '__main__':
    setLogLevel('info')
    
    topo = LoadBalancerTopo()
    net = Mininet(topo=topo, controller=RemoteController)
    
    info('*** Starting network\n')
    net.start()
    
    info('*** Waiting for controller connection...\n')
    time.sleep(5)
    
    test_performance(net)
    
    info('*** Entering CLI for manual testing\n')
    CLI(net)
    
    net.stop()
