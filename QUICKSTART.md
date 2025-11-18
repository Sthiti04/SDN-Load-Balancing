# Quick Start Guide

**Get up and running in 5 minutes!**

---

## 🚀 For First Time Setup

```bash
# 1. Install prerequisites
sudo apt update
sudo apt install -y mininet openvswitch-switch python3 python3-venv git build-essential

# 2. Clone the repository
git clone https://github.com/Sthiti04/SDN-Load-Balancing.git
cd SDN-Load-Balancing

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Ryu (with Python 3.12+ fix)
cd /tmp
git clone https://github.com/faucetsdn/ryu.git
cd ryu
sed -i '36,37d' ryu/hooks.py
cd ~/sthiti-sdn-lb
pip install --upgrade pip
pip install "setuptools<58"
cd /tmp/ryu && pip install .
pip install --upgrade eventlet "dnspython>=2.0.0" setuptools==74.0.0

# 5. Clone/copy your project files to ~/sthiti-sdn-lb/

# 6. Verify setup
cd /home/thread/SDN-Load-Balancing
./test_setup.sh
```

---

## 🎮 Running the System

### Every Time You Want to Run:

**Terminal 1:**
```bash
cd /home/thread/SDN-Load-Balancing
sudo python3 topo.py
```

**Terminal 2:**
```bash
cd /home/thread/SDN-Load-Balancing
source venv/bin/activate
ryu-manager static_select.py  # or any other controller
```

---

## 🧪 Quick Test

In Mininet terminal:
```bash
mininet> pingall
mininet> h1 ping h2
```

---

## 🛑 Stopping

**Terminal 1 (Mininet):**
```bash
mininet> exit
```

**Terminal 2 (Ryu):**
```
Ctrl+C
```

**Cleanup:**
```bash
sudo mn -c
```

---

## 📖 Full Guide

See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for detailed instructions and troubleshooting.
