# SDN Load Balancing

OpenFlow-based load balancing implementation using Ryu SDN controller and Mininet.

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get running in 5 minutes ⚡
- **[Complete Installation Guide](INSTALLATION_GUIDE.md)** - Detailed setup instructions 📖
- **[Architecture Overview](ARCHITECTURE.md)** - System design and diagrams 🏗️
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues & solutions 🔧
- **[Setup Instructions](SETUP_INSTRUCTIONS.md)** - Configuration and usage details ⚙️

## 🚀 Quick Start

### Automated Installation

```bash
# Download and run the installer
curl -O https://raw.githubusercontent.com/Sthiti04/SDN-Load-Balancing/main/install.sh
chmod +x install.sh
./install.sh
```

### Manual Installation

```bash
# Install prerequisites
sudo apt install -y mininet openvswitch-switch python3 python3-venv

# Set up project
mkdir -p ~/sthiti-sdn-lb
cd ~/sthiti-sdn-lb
python3 -m venv venv
source venv/bin/activate

# Install Ryu (see INSTALLATION_GUIDE.md for Python 3.12+ fix)
pip install ryu
```

## 🎮 Running the System

### Terminal 1: Start Topology
```bash
cd ~/sthiti-sdn-lb
sudo python3 topo.py
```

### Terminal 2: Start Controller
```bash
cd ~/sthiti-sdn-lb
source venv/bin/activate
ryu-manager static_select.py
```

## 🎯 Available Controllers

| Controller | Description |
|------------|-------------|
| `static_select.py` | Static hash-based selection with fast failover |
| `static_round_robin.py` | Round-robin with failover groups |
| `dynamic_least_load.py` | Least-load balancing with monitoring |
| `dynamic_dwrs.py` | Dynamic Weighted Round-Robin (binary search) |
| `hybrid.py` | Adaptive static/dynamic switching |

## 🧪 Testing

```bash
# Run setup verification
./test_setup.sh

# In Mininet CLI
mininet> pingall
mininet> h1 ping h2
```

## 📊 Network Topology

- **VIP:** 10.0.0.100
- **Client:** h1 (10.0.0.1)
- **Servers:** h2-h5 (10.0.0.2-10.0.0.5)
- **Switch:** s1 (OpenFlow 1.3)

## 🛠️ Requirements

- Ubuntu 22.04+ (or WSL2)
- Python 3.10+
- Mininet 2.3.0+
- Ryu SDN Framework 4.34
- Open vSwitch

## 📖 For More Information

See the complete [Installation Guide](INSTALLATION_GUIDE.md) for:
- Detailed installation steps
- Troubleshooting tips
- Advanced configuration
- Load balancing algorithms explained
