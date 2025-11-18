# SDN Load Balancing

OpenFlow-based load balancing implementation using Ryu SDN controller and Mininet.

## ⚠️ Important: Virtual Environment

**The `venv/` directory is NOT included in this repository.** Each user must create their own virtual environment using the `install.sh` script or by following the [Installation Guide](INSTALLATION_GUIDE.md).

This is intentional because virtual environments:
- Are machine-specific with absolute paths
- Don't work across different systems
- Should never be committed to version control

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get running in 5 minutes ⚡
- **[Complete Installation Guide](INSTALLATION_GUIDE.md)** - Detailed setup instructions 📖
- **[Architecture Overview](ARCHITECTURE.md)** - System design and diagrams 🏗️
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues & solutions 🔧
- **[Performance Results](PERFORMANCE_RESULTS.md)** - Test metrics and benchmarks 📊

## 🚀 Quick Start

### Option 1: Automated Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/Sthiti04/SDN-Load-Balancing.git
cd SDN-Load-Balancing

# Run the automated installer
chmod +x install.sh
./install.sh
```

### Option 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/Sthiti04/SDN-Load-Balancing.git
cd SDN-Load-Balancing

# Install prerequisites
sudo apt install -y mininet openvswitch-switch python3 python3-venv build-essential

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Ryu with Python 3.12+ compatibility fix
cd /tmp
git clone https://github.com/faucetsdn/ryu.git
cd ryu
sed -i '36,37d' ryu/hooks.py
pip install "setuptools<58"
pip install .
pip install --upgrade eventlet==0.40.3 "dnspython>=2.0.0" setuptools==74.0.0
```

## 🎮 Running the System

### Terminal 1: Start Topology
```bash
sudo python3 topo.py
```

### Terminal 2: Start Controller
```bash
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

### Automated Testing Scripts

Three test scripts are available for different scenarios:

```bash
# 1. Verify installation and dependencies
./test_setup.sh

# 2. Basic performance test (no controller required)
#    Tests: connectivity, latency, TCP/UDP throughput with OVS controller
sudo python3 test_basic.py

# 3. Automated performance test (no controller required)
#    Comprehensive tests without manual interaction
sudo python3 test_automated.py

# 4. Test with Ryu controller (start controller first)
#    Terminal 1: source venv/bin/activate && ryu-manager hybrid.py
#    Terminal 2: sudo python3 test_hybrid_performance.py
```

### Manual Testing in Mininet CLI

```bash
mininet> pingall
mininet> h1 ping h2
mininet> iperf h1 h2
```

See [PERFORMANCE_RESULTS.md](PERFORMANCE_RESULTS.md) for detailed test results.

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

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. **Do NOT commit venv/** (already in .gitignore)
4. Commit your changes
5. Push to the branch
6. Create a Pull Request

## 📖 For More Information

See the complete [Installation Guide](INSTALLATION_GUIDE.md) for:
- Detailed installation steps
- Troubleshooting tips
- Advanced configuration
- Load balancing algorithms explained
