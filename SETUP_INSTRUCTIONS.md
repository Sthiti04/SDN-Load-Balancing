# SDN Load Balancer - Setup Complete! ✅

## Summary of Changes

1. **Fixed Bug**: Corrected IP address typo in `dynamic_dwrs.py` (line 3 had `10:00:00:00:00:03` → fixed to `10.0.0.3`)

2. **Updated Topology**: Changed from `Controller` to `RemoteController` to work with Ryu SDN controller

3. **Installed Dependencies**:
   - Python 3.12 (already present)
   - Mininet (already present)
   - Open vSwitch (already present)
   - Ryu 4.34 (installed in virtual environment)
   - Fixed Python 3.12 compatibility issues with eventlet and dnspython

4. **Created Helper Scripts**:
   - `test_setup.sh` - Verify all components are properly installed
   - `run_controller.sh` - Easy way to start any controller

## Quick Test

Before running the full system, verify everything is set up correctly:

```bash
cd /home/thread/SDN-Load-Balancing
./test_setup.sh
```

This will check all dependencies and controller files for errors.

## How to Run Your Code

### Option 1: Manual Method (Two Terminals)

**Terminal 1 - Start the Mininet Topology:**
```bash
cd /home/thread/SDN-Load-Balancing
sudo python3 topo.py
```

**Terminal 2 - Start a Controller:**
```bash
cd /home/thread/SDN-Load-Balancing
source venv/bin/activate
ryu-manager static_select.py
# OR any other controller:
# ryu-manager static_round_robin.py
# ryu-manager dynamic_least_load.py
# ryu-manager dynamic_dwrs.py
# ryu-manager hybrid.py
```

### Option 2: Using the Helper Script

**Terminal 1 - Topology:**
```bash
cd /home/thread/SDN-Load-Balancing
sudo python3 topo.py
```

**Terminal 2 - Controller:**
```bash
cd /home/thread/SDN-Load-Balancing
./run_controller.sh static_select.py
```

## Available Controllers

1. **static_select.py** - Static hash-based selection with fast failover
2. **static_round_robin.py** - Round-robin with fast failover groups
3. **dynamic_least_load.py** - Least-load balancing with port monitoring
4. **dynamic_dwrs.py** - Dynamic Weighted Round-Robin with binary search
5. **hybrid.py** - Hybrid approach that switches between static/dynamic based on load variance

## Testing in Mininet CLI

Once both topology and controller are running, in the Mininet CLI you can test:

```bash
# Test connectivity
mininet> pingall

# Check hosts
mininet> nodes

# Test HTTP server on hosts
mininet> h2 python3 -m http.server 80 &
mininet> h3 python3 -m http.server 80 &
mininet> h4 python3 -m http.server 80 &
mininet> h5 python3 -m http.server 80 &

# Send requests from client
mininet> h1 curl 10.0.0.100
```

## Troubleshooting

### If Open vSwitch is not running:
```bash
sudo /usr/share/openvswitch/scripts/ovs-ctl start
```

### If you get "command not found" for ryu-manager:
```bash
source venv/bin/activate
```

### To completely restart:
1. In Mininet terminal: Press Ctrl+D or type `exit`
2. Clean up: `sudo mn -c`
3. Restart topology and controller

## Virtual Environment

The virtual environment is located at `/home/thread/SDN-Load-Balancing/venv/`

**Important:** Each user must create their own virtual environment. The venv/ directory is not included in the git repository.

To activate it:
```bash
cd /home/thread/SDN-Load-Balancing
source venv/bin/activate
```

To deactivate:
```bash
deactivate
```

## Notes

- Always run `topo.py` with `sudo` (Mininet requires root)
- Run controllers inside the virtual environment
- Make sure to activate venv before running controllers
- The VIP (Virtual IP) is configured as `10.0.0.100` in all controllers
- Client is on `h1` (10.0.0.1), servers are on `h2-h5` (10.0.0.2-5)
