# Performance Testing Results Summary

## Test Environment
- **Date**: November 18, 2025
- **Topology**: 1 client (h1), 4 servers (h2-h5), 1 switch (s1)
- **Controller**: Tested with OVSController (basic) and Hybrid SDN Controller
- **Network**: Star topology with OpenFlow 1.3

## Test Scripts Created

### 1. test_automated.py
Fully automated performance test without requiring SDN controller interaction.
- Uses OVSController for basic L2 forwarding
- No manual CLI interaction needed
- Generates results_basic.txt output file

### 2. test_hybrid_performance.py  
Comprehensive test designed for the Hybrid SDN Load Balancer controller.
- Connects to Ryu controller at port 6653
- Tests VIP functionality
- Detailed metrics extraction

### 3. test_basic.py
Interactive test with Mininet CLI access for manual testing.

## Performance Metrics Collected

### ✅ Connectivity Test
- **Result**: 0% packet loss
- **Status**: All 5 hosts can communicate successfully
- **Test**: pingall command (20 pings total)

### ✅ Latency Measurements
Tested: Client (h1) → Each Server (h2-h5)

| Server | Min (ms) | Avg (ms) | Max (ms) | Std Dev (ms) |
|--------|----------|----------|----------|--------------|
| h2     | 0.058    | 0.096    | 0.292    | 0.066        |
| h3     | 0.048    | 0.135    | 0.753    | 0.206        |
| h4     | 0.054    | 0.125    | 0.566    | 0.148        |
| h5     | 0.059    | 0.117    | 0.433    | 0.110        |

**Average Latency**: ~0.118 ms  
**Packet Loss**: 0% across all servers

### ✅ Link Bandwidth
- **Link Speed**: 10 Gbps (10000 Mb/s) per link
- **All Links**: h1-eth0, h2-eth0, h3-eth0, h4-eth0, h5-eth0

### ✅ UDP Throughput Test
- **Target**: 50 Mbps per server
- **Duration**: 5 seconds per test
- **Datagrams Sent**: ~22,294 datagrams per server
- **Result**: Successfully transmitted UDP traffic to all 4 servers

### ✅ Switch Port Statistics
Successfully captured per-port statistics showing:
- Packets received (rx pkts)
- Packets transmitted (tx pkts)  
- Bytes transferred
- Drop/error counters (all 0)

**Sample Data**:
- s1-eth1 (client): 127,767 rx pkts, 194,360 tx pkts, 7.9 GB transmitted
- s1-eth5: 762,129 rx pkts, 31.1 GB received
- **No packet drops or errors detected**

## TCP Throughput Tests
TCP throughput tests were executed but results need better parsing in the output.
- iperf servers started successfully on all 4 servers
- Tests ran for 5 seconds each
- Connection established but throughput values need extraction improvement

## Commands Used

### Basic Performance Test
```bash
cd /home/thread/SDN-Load-Balancing
sudo python3 test_automated.py
```

### With Hybrid Controller
**Terminal 1 - Start Controller:**
```bash
cd /home/thread/SDN-Load-Balancing
source venv/bin/activate
ryu-manager --verbose hybrid.py
```

**Terminal 2 - Run Tests:**
```bash
cd /home/thread/SDN-Load-Balancing
sudo python3 test_hybrid_performance.py
```

## Key Findings

### ✅ Working Features
1. **Perfect Connectivity**: 0% packet loss between all hosts
2. **Low Latency**: Sub-millisecond average latency (~0.12ms)
3. **High Bandwidth Links**: 10 Gbps links functioning properly
4. **UDP Traffic**: Successfully handles UDP flows at 50 Mbps target
5. **Switch Performance**: No packet drops or errors at switch level

### ⚠ Notes
1. **Hybrid Controller**: Has some initialization issues with OFPBucket syntax
2. **TCP Metrics**: Throughput values captured but need better parsing
3. **VIP Testing**: Requires controller fixes before full load balancer testing

## Next Steps for Full Load Balancer Testing

1. Fix the OFPBucket initialization in hybrid.py (line 143)
2. Correct the flow match prerequisites (OFPBMC_BAD_PREREQ error)
3. Re-test with VIP (10.0.0.100) functionality
4. Measure load distribution across servers
5. Test failover scenarios

## Files Generated
- `results_basic.txt` - Full output from automated test
- `test_automated.py` - Automated test script
- `test_hybrid_performance.py` - Hybrid controller test script
- `test_basic.py` - Interactive test script

## System Information
- **Ryu Version**: 4.34
- **Python Version**: 3.12
- **Mininet**: Installed and functional
- **Open vSwitch**: Running properly
- **Virtual Environment**: Created at /home/thread/SDN-Load-Balancing/venv
