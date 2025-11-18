# SDN Load Balancer - Complete Installation Guide

A step-by-step guide to set up and run this SDN-based load balancer on Ubuntu 22.04+ (including WSL).

---

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Step 1: System Update](#step-1-system-update)
- [Step 2: Install Mininet](#step-2-install-mininet)
- [Step 3: Install Open vSwitch](#step-3-install-open-vswitch)
- [Step 4: Set Up Python Environment](#step-4-set-up-python-environment)
- [Step 5: Install Ryu SDN Controller](#step-5-install-ryu-sdn-controller)
- [Step 6: Download Project Files](#step-6-download-project-files)
- [Step 7: Verify Installation](#step-7-verify-installation)
- [Step 8: Run the System](#step-8-run-the-system)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Ubuntu 22.04 or later (also works on WSL2)
- Sudo/root access
- Internet connection
- At least 2GB free disk space

---

## Step 1: System Update

Update your system packages:

```bash
sudo apt update
sudo apt upgrade -y
```

---

## Step 2: Install Mininet

Mininet is a network emulator that creates virtual networks.

### Option A: Quick Install (Recommended)

```bash
sudo apt install -y mininet
```

### Option B: Install from Source (Latest Version)

```bash
sudo apt install -y git
git clone https://github.com/mininet/mininet
cd mininet
sudo PYTHON=python3 util/install.sh -a
cd ..
```

### Verify Mininet Installation

```bash
sudo mn --version
```

Expected output: `2.3.0` or higher

---

## Step 3: Install Open vSwitch

Open vSwitch is required for OpenFlow support:

```bash
sudo apt install -y openvswitch-switch
```

### Start Open vSwitch Service

```bash
sudo systemctl start openvswitch-switch
sudo systemctl enable openvswitch-switch
```

**WSL Users:** If systemctl doesn't work, use:
```bash
sudo /usr/share/openvswitch/scripts/ovs-ctl start
```

### Verify Open vSwitch Installation

```bash
sudo ovs-vsctl --version
```

---

## Step 4: Set Up Python Environment

### Install Python 3 and Required Tools

```bash
sudo apt install -y python3 python3-pip python3-venv python3-dev
```

### Verify Python Installation

```bash
python3 --version
```

Expected output: `Python 3.10.x` or higher

---

## Step 5: Install Ryu SDN Controller

Ryu is the OpenFlow controller framework.

### Create Project Directory

```bash
mkdir -p ~/sthiti-sdn-lb
cd ~/sthiti-sdn-lb
```

### Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Build Dependencies

```bash
sudo apt install -y build-essential
```

### Clone and Patch Ryu (Python 3.12+ Compatibility)

```bash
cd /tmp
git clone https://github.com/faucetsdn/ryu.git
cd ryu

# Fix Python 3.12 compatibility
sed -i '36,37d' ryu/hooks.py
```

### Install Ryu

```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
pip install --upgrade pip
pip install "setuptools<58"
cd /tmp/ryu
pip install .
```

### Upgrade Dependencies for Python 3.12+

```bash
pip install --upgrade eventlet "dnspython>=2.0.0" setuptools==74.0.0
```

### Verify Ryu Installation

```bash
ryu-manager --version
```

Expected output: `ryu-manager 4.34`

---

## Step 6: Download Project Files

### Option A: If You Have Git Repository

```bash
cd ~/sthiti-sdn-lb
# Clone your repository here
git clone <your-repo-url> .
```

### Option B: Manual File Creation

If you have the files locally, copy them to `~/sthiti-sdn-lb/`:

Required files:
- `topo.py` - Network topology
- `static_select.py` - Static SELECT group controller
- `static_round_robin.py` - Round-robin controller
- `dynamic_least_load.py` - Least-load controller
- `dynamic_dwrs.py` - DWRS controller
- `hybrid.py` - Hybrid controller

---

## Step 7: Verify Installation

### Run the Test Script

```bash
cd ~/sthiti-sdn-lb
chmod +x test_setup.sh
./test_setup.sh
```

You should see:
```
✅ All checks passed!
```

### Clean Any Previous Mininet State

```bash
sudo mn -c
```

---

## Step 8: Run the System

### Open Two Terminal Windows

#### Terminal 1: Start the Topology

```bash
cd ~/sthiti-sdn-lb
sudo python3 topo.py
```

Wait for the message:
```
*** Starting controller
c0
*** Starting 1 switches
s1
Custom topology with 1 client and 4 server hosts
Waiting for remote controller on localhost:6653...
mininet>
```

#### Terminal 2: Start the Controller

In a new terminal:

```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
ryu-manager static_select.py
```

**Or use any other controller:**
```bash
ryu-manager static_round_robin.py
ryu-manager dynamic_least_load.py
ryu-manager dynamic_dwrs.py
ryu-manager hybrid.py
```

### Test the Setup

In the Mininet terminal (Terminal 1), run:

```bash
mininet> pingall
```

Expected output:
```
*** Ping: testing ping reachability
h1 -> h2 h3 h4 h5
h2 -> h1 h3 h4 h5
h3 -> h1 h2 h4 h5
h4 -> h1 h2 h3 h5
h5 -> h1 h2 h3 h4
*** Results: 0% dropped (20/20 received)
```

### Test Load Balancing

In Mininet terminal:

```bash
# Start simple HTTP servers on backend servers
mininet> h2 python3 -m http.server 80 &
mininet> h3 python3 -m http.server 80 &
mininet> h4 python3 -m http.server 80 &
mininet> h5 python3 -m http.server 80 &

# Send requests from client to VIP
mininet> h1 curl 10.0.0.100
```

### Stop the System

**In Terminal 1 (Mininet):**
```bash
mininet> exit
```

**In Terminal 2 (Controller):**
Press `Ctrl+C`

**Clean up:**
```bash
sudo mn -c
```

---

## 🎯 Quick Reference Commands

### Activate Virtual Environment
```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
```

### Deactivate Virtual Environment
```bash
deactivate
```

### Clean Mininet State
```bash
sudo mn -c
```

### Check Ryu Version
```bash
source ~/sthiti-sdn-lb/venv/bin/activate
ryu-manager --version
```

### Run Test Script
```bash
cd ~/sthiti-sdn-lb
./test_setup.sh
```

---

## 📊 Available Controllers

| Controller | Description | Algorithm |
|------------|-------------|-----------|
| `static_select.py` | Hash-based selection with failover | OpenFlow SELECT group |
| `static_round_robin.py` | Round-robin distribution | Controller-driven RR |
| `dynamic_least_load.py` | Least connections | Real-time load monitoring |
| `dynamic_dwrs.py` | Weighted round-robin | Binary search DWRS |
| `hybrid.py` | Adaptive switching | Static ↔ Dynamic based on variance |

---

## 🐛 Troubleshooting

### Issue: "externally-managed-environment" Error

**Solution:** Always use virtual environment:
```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
pip install <package>
```

### Issue: "Cannot find required executable controller"

**Solution:** This is expected - the topology uses RemoteController. Make sure to start `ryu-manager` in Terminal 2.

### Issue: "Unable to contact the remote controller"

**Solution:** 
1. Make sure Terminal 2 (Ryu) is running
2. Check that Ryu is listening on port 6653:
```bash
netstat -tulpn | grep 6653
```

### Issue: Open vSwitch Not Running (WSL)

**Solution:**
```bash
sudo /usr/share/openvswitch/scripts/ovs-ctl start
```

### Issue: "No module named 'ryu'"

**Solution:** Activate virtual environment:
```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
```

### Issue: Mininet Permission Denied

**Solution:** Always run Mininet with sudo:
```bash
sudo python3 topo.py
```

### Issue: Port Already in Use

**Solution:**
```bash
# Kill existing processes
sudo mn -c
sudo killall ryu-manager
```

### Issue: Virtual Environment Corrupted

**Solution:** Recreate it:
```bash
cd ~/sthiti-sdn-lb
rm -rf venv
python3 -m venv venv
source venv/bin/activate
# Re-run Step 5
```

---

## 📝 Network Configuration

### Topology Details

- **VIP (Virtual IP):** 10.0.0.100
- **Client:** h1 (10.0.0.1)
- **Servers:**
  - h2 (10.0.0.2)
  - h3 (10.0.0.3)
  - h4 (10.0.0.4)
  - h5 (10.0.0.5)
- **Switch:** s1 (OpenFlow 1.3)

### OpenFlow Controller

- **Protocol:** OpenFlow 1.3
- **Port:** 6653 (default)
- **Address:** 127.0.0.1 (localhost)

---

## 🔧 Advanced Configuration

### Change Controller Port

Edit controller files and change:
```python
# Default is 6653
# To use different port, start ryu-manager with:
ryu-manager --ofp-tcp-listen-port 6633 static_select.py
```

Then update `topo.py`:
```python
net = Mininet(topo=topo, controller=lambda name: RemoteController(name, port=6633))
```

### Enable Verbose Logging

```bash
ryu-manager --verbose static_select.py
```

### View OpenFlow Flows

In Mininet terminal:
```bash
mininet> sh ovs-ofctl dump-flows s1
```

### View Group Tables

```bash
mininet> sh ovs-ofctl -O OpenFlow13 dump-groups s1
```

---

## 📚 Additional Resources

- [Mininet Documentation](http://mininet.org/walkthrough/)
- [Ryu SDN Framework](https://ryu-sdn.org/)
- [OpenFlow Specification](https://opennetworking.org/software-defined-standards/specifications/)
- [Open vSwitch Documentation](https://www.openvswitch.org/)

---

## ✅ Post-Installation Checklist

- [ ] Python 3.10+ installed
- [ ] Mininet installed and tested
- [ ] Open vSwitch installed and running
- [ ] Virtual environment created
- [ ] Ryu controller installed
- [ ] All project files present
- [ ] `test_setup.sh` passes all checks
- [ ] Topology starts without errors
- [ ] Controller connects successfully
- [ ] `pingall` works in Mininet

---

## 🎓 Learning Path

1. **Start Simple:** Run `static_select.py` first
2. **Test Failover:** Bring down a server link and observe failover
3. **Monitor Traffic:** Use `ovs-ofctl dump-flows` to see flow entries
4. **Try Dynamic:** Switch to `dynamic_least_load.py`
5. **Advanced:** Test `hybrid.py` with varying loads

---

## 📧 Support

If you encounter issues not covered in this guide, check:
1. All commands were run in the correct directory
2. Virtual environment is activated when needed
3. All prerequisites are properly installed
4. No other services are using port 6653

---

**Last Updated:** November 2025  
**Tested On:** Ubuntu 22.04 LTS, Ubuntu 24.04 LTS, WSL2 (Ubuntu 22.04)
