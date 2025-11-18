#!/usr/bin/env python3
"""
Complete Performance Test for SDN Load Balancer with Hybrid Controller
Tests throughput (TCP/UDP), latency, and per-link bandwidth
"""

from mininet.net import Mininet
from mininet.node import RemoteController
from mininet.log import setLogLevel, info
from topo import LoadBalancerTopo
import time
import re

def extract_throughput(output):
    """Extract throughput from iperf output"""
    for line in output.split('\n'):
        if 'bits/sec' in line and '[' in line:
            # Extract bandwidth value
            match = re.search(r'([\d.]+)\s+(Mbits|Gbits)/sec', line)
            if match:
                value = float(match.group(1))
                unit = match.group(2)
                if unit == 'Gbits':
                    value *= 1000
                return f"{value:.2f} Mbits/sec"
    return "N/A"

def extract_latency(output):
    """Extract latency stats from ping output"""
    for line in output.split('\n'):
        if 'rtt min/avg/max/mdev' in line:
            match = re.search(r'= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)', line)
            if match:
                return {
                    'min': float(match.group(1)),
                    'avg': float(match.group(2)),
                    'max': float(match.group(3)),
                    'mdev': float(match.group(4))
                }
    return None

def test_with_hybrid_controller(net):
    """Run performance tests with hybrid load balancer"""
    
    client = net.get('h1')
    servers = [net.get(f'h{i}') for i in range(2, 6)]
    
    print('\n' + '='*70)
    print('SDN LOAD BALANCER PERFORMANCE TEST - HYBRID CONTROLLER')
    print('='*70)
    
    # Test 1: Connectivity
    print('\n[TEST 1] CONNECTIVITY TEST')
    print('-'*70)
    info('Running pingall...\n')
    loss = net.pingAll()
    print(f'✓ Packet loss: {loss}%')
    if loss == 0:
        print('✓ All hosts can communicate')
    
    # Test 2: Latency to each server
    print('\n[TEST 2] LATENCY MEASUREMENTS (Direct to Servers)')
    print('-'*70)
    latencies = {}
    for i in range(2, 6):
        result = client.cmd(f'ping -c 10 -i 0.2 10.0.0.{i}')
        stats = extract_latency(result)
        if stats:
            latencies[f'h{i}'] = stats
            print(f'h{i} (10.0.0.{i}): min={stats["min"]:.3f}ms, avg={stats["avg"]:.3f}ms, '
                  f'max={stats["max"]:.3f}ms, mdev={stats["mdev"]:.3f}ms')
    
    # Test 3: VIP connectivity (if controller supports it)
    print('\n[TEST 3] VIP CONNECTIVITY TEST')
    print('-'*70)
    print('Testing connectivity to VIP (10.0.0.100)...')
    result = client.cmd('ping -c 5 -W 2 10.0.0.100')
    if '0% packet loss' in result:
        print('✓ VIP is reachable')
        stats = extract_latency(result)
        if stats:
            print(f'VIP latency: avg={stats["avg"]:.3f}ms')
    else:
        print('⚠ VIP not reachable (controller may need adjustment)')
    
    # Test 4: TCP throughput to each server
    print('\n[TEST 4] TCP THROUGHPUT TEST (Direct to Each Server)')
    print('-'*70)
    
    # Start iperf servers
    for i, server in enumerate(servers, start=2):
        port = 5000 + i
        server.cmd(f'iperf -s -p {port} > /tmp/iperf_s{i}.log 2>&1 &')
    
    time.sleep(2)
    
    tcp_results = {}
    for i in range(2, 6):
        port = 5000 + i
        result = client.cmd(f'iperf -c 10.0.0.{i} -p {port} -t 5')
        throughput = extract_throughput(result)
        tcp_results[f'h{i}'] = throughput
        print(f'h{i} (10.0.0.{i}): {throughput}')
    
    # Test 5: UDP throughput
    print('\n[TEST 5] UDP THROUGHPUT TEST (50Mbps target)')
    print('-'*70)
    
    udp_results = {}
    for i in range(2, 6):
        port = 5000 + i
        result = client.cmd(f'iperf -c 10.0.0.{i} -p {port} -u -b 50M -t 5')
        throughput = extract_throughput(result)
        udp_results[f'h{i}'] = throughput
        # Extract packet loss
        loss_match = re.search(r'\((\d+)%\)', result)
        loss_str = f", {loss_match.group(1)}% loss" if loss_match else ""
        print(f'h{i} (10.0.0.{i}): {throughput}{loss_str}')
    
    # Test 6: Link bandwidth
    print('\n[TEST 6] LINK BANDWIDTH INFORMATION')
    print('-'*70)
    for i in range(1, 6):
        host = net.get(f'h{i}')
        result = host.cmd(f'ethtool h{i}-eth0 2>/dev/null | grep Speed')
        speed = result.strip().replace('Speed: ', '') if result.strip() else 'Unknown'
        print(f'h{i}-eth0: {speed}')
    
    # Test 7: Switch statistics
    print('\n[TEST 7] SWITCH PORT STATISTICS')
    print('-'*70)
    result = client.cmd('ovs-ofctl dump-ports s1')
    print(result)
    
    # Test 8: Flow table
    print('\n[TEST 8] OPENFLOW FLOW TABLE')
    print('-'*70)
    result = client.cmd('ovs-ofctl dump-flows s1')
    print(result)
    
    # Cleanup
    for server in servers:
        server.cmd('killall -9 iperf 2>/dev/null')
    
    # Summary
    print('\n' + '='*70)
    print('PERFORMANCE TEST SUMMARY')
    print('='*70)
    print(f'Connectivity: {100-loss}% success rate')
    print(f'Latency (avg): {sum(s["avg"] for s in latencies.values())/len(latencies):.3f}ms')
    print(f'TCP Throughput: {len([t for t in tcp_results.values() if t != "N/A"])}/4 servers tested')
    print(f'UDP Throughput: {len([t for t in udp_results.values() if t != "N/A"])}/4 servers tested')
    print(f'Link Speed: 10 Gbps per link')
    print('='*70)

if __name__ == '__main__':
    setLogLevel('info')
    
    print('\n' + '='*70)
    print('STARTING SDN TOPOLOGY WITH REMOTE CONTROLLER')
    print('='*70)
    print('Connecting to controller at 127.0.0.1:6653')
    print('Make sure the Ryu controller is running!')
    print('='*70)
    
    topo = LoadBalancerTopo()
    net = Mininet(topo=topo, controller=RemoteController)
    
    info('\n*** Starting network\n')
    net.start()
    
    info('*** Waiting for controller connection...\n')
    time.sleep(5)
    
    test_with_hybrid_controller(net)
    
    info('\n*** Stopping network\n')
    net.stop()
    
    print('\n✓ Performance test completed successfully!')
