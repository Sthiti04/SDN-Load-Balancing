#!/bin/bash

#########################################################
# SDN Load Balancer - Automated Installation Script
# For Ubuntu 22.04+ and WSL2
#########################################################

set -e  # Exit on any error

echo "=========================================="
echo "SDN Load Balancer - Automated Installer"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

# Check if running on Ubuntu
if [ ! -f /etc/os-release ]; then
    print_error "Cannot detect OS. This script is designed for Ubuntu."
    exit 1
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
    print_error "This script is designed for Ubuntu. Detected: $ID"
    exit 1
fi

print_success "Detected Ubuntu $VERSION_ID"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
    print_error "Please do not run this script as root (don't use sudo)"
    exit 1
fi

# Step 1: Update system
print_info "Step 1/7: Updating system packages..."
sudo apt update -qq
print_success "System updated"
echo ""

# Step 2: Install Mininet
print_info "Step 2/7: Installing Mininet..."
if command -v mn &> /dev/null; then
    print_success "Mininet already installed ($(mn --version 2>&1))"
else
    sudo apt install -y mininet > /dev/null 2>&1
    print_success "Mininet installed"
fi
echo ""

# Step 3: Install Open vSwitch
print_info "Step 3/7: Installing Open vSwitch..."
if command -v ovs-vsctl &> /dev/null; then
    print_success "Open vSwitch already installed"
else
    sudo apt install -y openvswitch-switch > /dev/null 2>&1
    print_success "Open vSwitch installed"
fi

# Start OVS service
if systemctl is-active --quiet openvswitch-switch 2>/dev/null; then
    print_success "Open vSwitch service is running"
else
    print_info "Starting Open vSwitch service..."
    if sudo systemctl start openvswitch-switch 2>/dev/null; then
        sudo systemctl enable openvswitch-switch 2>/dev/null
        print_success "Open vSwitch service started"
    else
        # WSL fallback
        print_info "Systemctl not available, using manual start (WSL mode)"
        sudo /usr/share/openvswitch/scripts/ovs-ctl start > /dev/null 2>&1 || true
        print_success "Open vSwitch started"
    fi
fi
echo ""

# Step 4: Install Python dependencies
print_info "Step 4/7: Installing Python and build tools..."
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential git > /dev/null 2>&1
print_success "Python $(python3 --version | cut -d' ' -f2) installed"
echo ""

# Step 5: Create virtual environment
print_info "Step 5/7: Setting up Python virtual environment..."
PROJECT_DIR="$HOME/sthiti-sdn-lb"

if [ -d "$PROJECT_DIR/venv" ]; then
    print_info "Virtual environment already exists, recreating..."
    rm -rf "$PROJECT_DIR/venv"
fi

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
print_success "Virtual environment created"
echo ""

# Step 6: Install Ryu SDN Controller
print_info "Step 6/7: Installing Ryu SDN Controller..."

# Clone Ryu if not exists
if [ ! -d "/tmp/ryu" ]; then
    print_info "Cloning Ryu repository..."
    cd /tmp
    git clone https://github.com/faucetsdn/ryu.git > /dev/null 2>&1
    print_success "Ryu cloned"
else
    print_success "Ryu repository already exists"
fi

# Patch Ryu for Python 3.12+ compatibility
print_info "Patching Ryu for Python 3.12+ compatibility..."
cd /tmp/ryu
sed -i '36,37d' ryu/hooks.py 2>/dev/null || true

# Install Ryu
cd "$PROJECT_DIR"
source venv/bin/activate

print_info "Installing Ryu and dependencies (this may take a minute)..."
pip install --quiet --upgrade pip
pip install --quiet "setuptools<58"
cd /tmp/ryu
pip install --quiet .
pip install --quiet --upgrade eventlet "dnspython>=2.0.0" setuptools==74.0.0

# Verify installation
if command -v ryu-manager &> /dev/null; then
    print_success "Ryu $(ryu-manager --version 2>&1) installed"
else
    print_error "Ryu installation failed"
    exit 1
fi
echo ""

# Step 7: Verify everything
print_info "Step 7/7: Verifying installation..."
cd "$PROJECT_DIR"

# Create a simple test
echo "Testing components..."

# Test Python
python3 -c "import sys; assert sys.version_info >= (3, 10)" && print_success "Python check passed"

# Test Mininet
sudo mn -c > /dev/null 2>&1
print_success "Mininet check passed"

# Test OVS
sudo ovs-vsctl show > /dev/null 2>&1 && print_success "Open vSwitch check passed"

# Test Ryu
source venv/bin/activate
ryu-manager --version > /dev/null 2>&1 && print_success "Ryu check passed"

echo ""
echo "=========================================="
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo "=========================================="
echo ""
echo "Project directory: $PROJECT_DIR"
echo ""
echo "Next steps:"
echo ""
echo "1. Copy your project files to: $PROJECT_DIR"
echo "   - topo.py"
echo "   - static_select.py"
echo "   - static_round_robin.py"
echo "   - dynamic_least_load.py"
echo "   - dynamic_dwrs.py"
echo "   - hybrid.py"
echo ""
echo "2. Run the test script:"
echo "   cd $PROJECT_DIR"
echo "   ./test_setup.sh"
echo ""
echo "3. Start the system:"
echo ""
echo "   Terminal 1:"
echo "   cd $PROJECT_DIR"
echo "   sudo python3 topo.py"
echo ""
echo "   Terminal 2:"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   ryu-manager static_select.py"
echo ""
echo "For detailed instructions, see:"
echo "   $PROJECT_DIR/INSTALLATION_GUIDE.md"
echo ""
