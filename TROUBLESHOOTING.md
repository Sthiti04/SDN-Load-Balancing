# Troubleshooting Cheat Sheet

Quick solutions to common issues.

---

## 🔴 Installation Issues

### "externally-managed-environment" error
```bash
# Always use virtual environment
cd ~/sthiti-sdn-lb
source venv/bin/activate
pip install <package>
```

### Ryu won't install on Python 3.12+
```bash
# Apply the compatibility fix
cd /tmp
git clone https://github.com/faucetsdn/ryu.git
cd ryu
sed -i '36,37d' ryu/hooks.py
pip install .
pip install --upgrade eventlet "dnspython>=2.0.0" setuptools==74.0.0
```

### "No module named 'distutils'"
```bash
pip install setuptools==74.0.0
```

---

## 🟡 Runtime Issues

### "Cannot find required executable controller"
**This is normal!** The topology uses RemoteController.
- Make sure ryu-manager is running in Terminal 2

### "Unable to contact the remote controller"
```bash
# 1. Check if Ryu is running
ps aux | grep ryu-manager

# 2. Check if port 6653 is in use
sudo netstat -tulpn | grep 6653

# 3. Start Ryu controller if not running
cd ~/sthiti-sdn-lb
source venv/bin/activate
ryu-manager static_select.py
```

### "Address already in use"
```bash
# Clean up existing processes
sudo mn -c
sudo killall ryu-manager
sudo killall python3
```

### Open vSwitch not running (WSL)
```bash
# Manual start
sudo /usr/share/openvswitch/scripts/ovs-ctl start

# Verify
sudo ovs-vsctl show
```

### Permission denied when running Mininet
```bash
# Always use sudo for Mininet
sudo python3 topo.py
```

---

## 🟢 Testing Issues

### pingall fails
```bash
# 1. Make sure controller is connected
# Check Terminal 2 for connection messages

# 2. Clean and restart
mininet> exit
sudo mn -c
# Restart both topology and controller

# 3. Check flows
mininet> sh ovs-ofctl dump-flows s1
```

### Hosts can't reach VIP (10.0.0.100)
```bash
# 1. Verify ARP is working
mininet> h1 arping -c 1 10.0.0.100

# 2. Check controller logs in Terminal 2

# 3. Verify flows for VIP
mininet> sh ovs-ofctl dump-flows s1 | grep "10.0.0.100"
```

---

## 🔧 Recovery Commands

### Complete reset
```bash
# Clean everything
sudo mn -c
sudo killall ryu-manager
sudo /usr/share/openvswitch/scripts/ovs-ctl restart

# Restart
cd ~/sthiti-sdn-lb
sudo python3 topo.py  # Terminal 1
source venv/bin/activate && ryu-manager static_select.py  # Terminal 2
```

### Recreate virtual environment
```bash
cd ~/sthiti-sdn-lb
rm -rf venv
python3 -m venv venv
source venv/bin/activate
# Re-run Ryu installation steps
```

### Check what's using port 6653
```bash
sudo lsof -i :6653
# or
sudo netstat -tulpn | grep 6653
```

---

## 📋 Diagnostic Commands

### Check Mininet installation
```bash
sudo mn --version
sudo mn --test pingall
```

### Check Open vSwitch
```bash
sudo ovs-vsctl show
sudo ovs-vsctl list-br
sudo ovs-ofctl show s1
```

### Check Ryu installation
```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
ryu-manager --version
which ryu-manager
```

### View OpenFlow flows
```bash
mininet> sh ovs-ofctl dump-flows s1
```

### View group tables
```bash
mininet> sh ovs-ofctl -O OpenFlow13 dump-groups s1
```

### Check controller connection
```bash
mininet> sh ovs-vsctl show
# Look for "is_connected: true"
```

---

## 🚨 Emergency Recovery

If everything is broken:

```bash
# 1. Kill all processes
sudo mn -c
sudo killall -9 ryu-manager python3 ovs-vswitchd ovsdb-server

# 2. Restart OVS
sudo /usr/share/openvswitch/scripts/ovs-ctl restart

# 3. Verify clean slate
sudo ovs-vsctl show  # Should show empty

# 4. Recreate venv if needed
cd ~/sthiti-sdn-lb
rm -rf venv
python3 -m venv venv
source venv/bin/activate
./install.sh  # Re-run installation

# 5. Start fresh
sudo python3 topo.py  # Terminal 1
source venv/bin/activate && ryu-manager static_select.py  # Terminal 2
```

---

## 📞 Still Having Issues?

1. Check all prerequisites are installed: `./test_setup.sh`
2. Review the [Installation Guide](INSTALLATION_GUIDE.md)
3. Make sure you're in the right directory: `cd ~/sthiti-sdn-lb`
4. Verify Python version: `python3 --version` (should be 3.10+)
5. Check system logs: `journalctl -xe | grep ovs`

---

## 💡 Tips

- Always activate venv before using Ryu: `source venv/bin/activate`
- Always use sudo for Mininet: `sudo python3 topo.py`
- Clean between runs: `sudo mn -c`
- One controller per topology at a time
- Terminal 1 = Topology (sudo), Terminal 2 = Controller (venv)
