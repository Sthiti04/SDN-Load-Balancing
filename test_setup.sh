#!/bin/bash
# Quick setup test script

echo "========================================="
echo "SDN Load Balancer Setup Test"
echo "========================================="
echo ""

# Check Python
echo "✓ Checking Python..."
python3 --version || { echo "✗ Python3 not found!"; exit 1; }

# Check Mininet
echo "✓ Checking Mininet..."
which mn > /dev/null || { echo "✗ Mininet not found!"; exit 1; }

# Check Open vSwitch
echo "✓ Checking Open vSwitch..."
which ovs-vsctl > /dev/null || { echo "✗ Open vSwitch not found!"; exit 1; }

# Check Virtual Environment
echo "✓ Checking Virtual Environment..."
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    echo "  Virtual environment exists"
else
    echo "✗ Virtual environment not found!"
    exit 1
fi

# Check Ryu
echo "✓ Checking Ryu installation..."
source venv/bin/activate
ryu-manager --version > /dev/null 2>&1 || { echo "✗ Ryu not installed!"; exit 1; }
echo "  $(ryu-manager --version)"

# Check topology file
echo "✓ Checking topology file..."
python3 -m py_compile topo.py || { echo "✗ Topology has syntax errors!"; exit 1; }

# Check controller files
echo "✓ Checking controller files..."
for controller in static_select.py static_round_robin.py dynamic_least_load.py dynamic_dwrs.py hybrid.py; do
    if [ -f "$controller" ]; then
        python3 -m py_compile "$controller" || { echo "✗ $controller has syntax errors!"; exit 1; }
        echo "  ✓ $controller"
    else
        echo "  ✗ $controller not found!"
    fi
done

echo ""
echo "========================================="
echo "✅ All checks passed!"
echo "========================================="
echo ""
echo "To run the system:"
echo ""
echo "Terminal 1 (Topology):"
echo "  cd ~/sthiti-sdn-lb"
echo "  sudo python3 topo.py"
echo ""
echo "Terminal 2 (Controller):"
echo "  cd ~/sthiti-sdn-lb"
echo "  source venv/bin/activate"
echo "  ryu-manager static_select.py"
echo ""
