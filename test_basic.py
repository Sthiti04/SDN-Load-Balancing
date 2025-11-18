#!/usr/bin/env python3
"""
Basic performance test without controller
Tests basic Mininet functionality and iperf
"""

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from topo import LoadBalancerTopo
import time

def test_basic(net):
    """Run basic performance tests"""
    
    client = net.get('h1')
    server1 = net.get('h2')
    
    info('\n*** Testing connectivity with pingall\n')
    net.pingAll()
    
    info('\n*** Testing ping latency from client to server1\n')
    result = client.cmd('ping -c 10 10.0.0.2')
    info(result)
    
    info('\n*** Starting iperf TCP server on h2\n')
    server1.cmd('iperf -s &')
    time.sleep(2)
    
    info('\n*** Running TCP throughput test (10 seconds)\n')
    result = client.cmd('iperf -c 10.0.0.2 -t 10')
    info(result)
    
    info('\n*** Running UDP throughput test (10 seconds, 10Mbps)\n')
    result = client.cmd('iperf -c 10.0.0.2 -u -b 10M -t 10')
    info(result)
    
    info('\n*** Link bandwidth information\n')
    result = client.cmd('ethtool h1-eth0 | grep -i speed')
    info(f'Client link: {result}')
    
    info('\n*** Test completed\n')

if __name__ == '__main__':
    setLogLevel('info')
    
    topo = LoadBalancerTopo()
    # Use OVS controller for basic testing
    net = Mininet(topo=topo, controller=OVSController)
    
    info('*** Starting network\n')
    net.start()
    
    test_basic(net)
    
    info('*** Entering CLI for additional testing\n')
    info('*** You can run commands like:\n')
    info('***   h1 ping h2\n')
    info('***   iperf h1 h2\n')
    CLI(net)
    
    net.stop()
