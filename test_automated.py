#!/usr/bin/env python3
"""
Automated Performance Test for SDN Load Balancer
Tests: throughput (TCP/UDP), latency, bandwidth
No manual interaction required
"""

from mininet.net import Mininet
from mininet.node import OVSController
from mininet.log import setLogLevel, info
from topo import LoadBalancerTopo
import time

def test_performance(net):
    """Run automated performance tests"""
    
    client = net.get('h1')
    servers = [net.get(f'h{i}') for i in range(2, 6)]
    
    print('\n' + '='*60)
    print('CONNECTIVITY TEST')
    print('='*60)
    info('\n*** Running pingall\n')
    loss = net.pingAll()
    print(f'Packet loss: {loss}%')
    
    print('\n' + '='*60)
    print('LATENCY TEST (Client to Each Server)')
    print('='*60)
    for i, server in enumerate(servers, start=2):
        info(f'\n*** Ping test: h1 -> h{i} (10.0.0.{i})\n')
        result = client.cmd(f'ping -c 10 -i 0.2 10.0.0.{i}')
        # Extract latency stats
        for line in result.split('\n'):
            if 'rtt min/avg/max' in line or 'packets transmitted' in line:
                print(line)
    
    print('\n' + '='*60)
    print('TCP THROUGHPUT TEST')
    print('='*60)
    
    # Start iperf servers on all servers
    for i, server in enumerate(servers, start=2):
        port = 5000 + i
        server.cmd(f'iperf -s -p {port} > /tmp/iperf_server_h{i}.log 2>&1 &')
        info(f'Started iperf server on h{i} port {port}\n')
    
    time.sleep(2)  # Wait for servers to start
    
    # Test TCP throughput to each server
    for i in range(2, 6):
        port = 5000 + i
        info(f'\n*** TCP test: h1 -> h{i} (port {port})\n')
        result = client.cmd(f'iperf -c 10.0.0.{i} -p {port} -t 5 -f M')
        # Extract throughput
        for line in result.split('\n'):
            if 'Mbits/sec' in line or 'Gbits/sec' in line:
                print(line)
    
    print('\n' + '='*60)
    print('UDP THROUGHPUT TEST')
    print('='*60)
    
    # Test UDP throughput to each server
    for i in range(2, 6):
        port = 5000 + i
        info(f'\n*** UDP test: h1 -> h{i} (port {port}, 50Mbps target)\n')
        result = client.cmd(f'iperf -c 10.0.0.{i} -p {port} -u -b 50M -t 5 -f M')
        # Extract throughput and packet loss
        for line in result.split('\n'):
            if 'Mbits/sec' in line or 'Gbits/sec' in line or 'datagrams' in line:
                print(line)
    
    print('\n' + '='*60)
    print('LINK BANDWIDTH INFO')
    print('='*60)
    
    # Get link info
    info('\n*** Checking link speeds\n')
    for i in range(1, 6):
        host = net.get(f'h{i}')
        result = host.cmd(f'ethtool h{i}-eth0 2>/dev/null | grep -i speed || echo "Speed: Unknown"')
        print(f'h{i}: {result.strip()}')
    
    # Get switch port info
    info('\n*** Switch port statistics\n')
    result = client.cmd('ovs-ofctl dump-ports s1')
    print(result)
    
    print('\n' + '='*60)
    print('TEST SUMMARY')
    print('='*60)
    print('✓ Connectivity test completed')
    print('✓ Latency measurements completed (10 pings per server)')
    print('✓ TCP throughput tests completed (5 sec per server)')
    print('✓ UDP throughput tests completed (5 sec per server)')
    print('✓ Link bandwidth information collected')
    print('='*60)
    
    # Kill iperf servers
    for server in servers:
        server.cmd('killall -9 iperf 2>/dev/null')

if __name__ == '__main__':
    setLogLevel('info')
    
    topo = LoadBalancerTopo()
    net = Mininet(topo=topo, controller=OVSController)
    
    info('*** Starting network\n')
    net.start()
    
    time.sleep(2)  # Let the network stabilize
    
    test_performance(net)
    
    info('\n*** Stopping network\n')
    net.stop()
    
    print('\nPerformance test completed!')
    print('For hybrid controller testing, start the controller first:')
    print('  Terminal 1: cd /home/thread/SDN-Load-Balancing && source venv/bin/activate && ryu-manager hybrid.py')
    print('  Terminal 2: cd /home/thread/SDN-Load-Balancing && sudo python3 test_performance.py')
