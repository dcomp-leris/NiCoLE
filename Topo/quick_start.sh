#!/bin/bash
#
# quick_start.sh - Quick setup and verification of L4S topology
# This script guides you through the setup process step by step
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROUTER_IP_100="192.168.100.2"
ROUTER_IP_200="192.168.200.2"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}===============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}===============================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_header "L4S Router Topology - Quick Start"

echo ""
echo "This guide will help you set up the L4S topology with:"
echo "  - h0, h1: Mininet hosts on 192.168.100.0/24"
echo "  - h2: Mininet host on 192.168.200.0/24"
echo "  - L4S Router VM: Routes traffic with DualQ on enp8s0"
echo ""

# Step 1: Check prerequisites
print_header "Step 1: Checking Prerequisites"

echo "Checking if running on host machine..."
if [[ -f /etc/hostname ]]; then
    HOSTNAME=$(cat /etc/hostname)
    echo "  Current hostname: $HOSTNAME"
fi

echo ""
echo "Checking if Mininet is installed..."
if command -v mn &> /dev/null; then
    print_success "Mininet is installed"
else
    print_error "Mininet not found! Install with: sudo apt install mininet"
    exit 1
fi

echo ""
echo "Checking if Python 3 is available..."
if command -v python3 &> /dev/null; then
    PYTHON_VER=$(python3 --version)
    print_success "$PYTHON_VER found"
else
    print_error "Python 3 not found!"
    exit 1
fi

echo ""
echo "Checking if traffic control (tc) is available..."
if command -v tc &> /dev/null; then
    print_success "Traffic control available"
else
    print_error "tc command not found! Install with: sudo apt install iproute2"
    exit 1
fi

# Step 2: Check router connectivity
print_header "Step 2: Checking Router Connectivity"

echo "Attempting to reach router at $ROUTER_IP_100..."
if ping -c 1 -W 2 $ROUTER_IP_100 &> /dev/null; then
    print_success "Can reach router at $ROUTER_IP_100"
else
    print_error "Cannot reach router at $ROUTER_IP_100"
    print_info "Make sure the L4S router VM (My-L4S-switch) is running"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "Attempting to reach router at $ROUTER_IP_200..."
if ping -c 1 -W 2 $ROUTER_IP_200 &> /dev/null; then
    print_success "Can reach router at $ROUTER_IP_200"
else
    print_error "Cannot reach router at $ROUTER_IP_200"
    print_info "Make sure the L4S router VM (My-L4S-switch) is running"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Step 3: Setup topology
print_header "Step 3: Setting Up Topology"

echo "Running topology setup script..."
if [[ -f "$SCRIPT_DIR/setup_topology.sh" ]]; then
    chmod +x "$SCRIPT_DIR/setup_topology.sh"
    if sudo "$SCRIPT_DIR/setup_topology.sh"; then
        print_success "Topology setup completed"
    else
        print_error "Topology setup failed!"
        exit 1
    fi
else
    print_error "setup_topology.sh not found at $SCRIPT_DIR"
    exit 1
fi

# Step 4: Verify setup
print_header "Step 4: Verifying Setup"

echo "Checking bridges..."
if ip link show br0 &> /dev/null; then
    print_success "Bridge br0 exists"
else
    print_error "Bridge br0 not found"
fi

if ip link show br1 &> /dev/null; then
    print_success "Bridge br1 exists"
else
    print_error "Bridge br1 not found"
fi

# Step 5: Ready to run
print_header "Step 5: Ready to Run Topology"

echo ""
echo "Everything is set up! You can now run the topology:"
echo ""
echo -e "  ${BLUE}sudo python3 $SCRIPT_DIR/topo1.py${NC}"
echo ""
echo "Once in Mininet CLI, test connectivity with:"
echo "  mininet> h0 ping h1"
echo "  mininet> h0 ping 192.168.200.10"
echo "  mininet> h2 ping 192.168.100.10"
echo ""

read -p "Run topology now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    print_info "Starting topology... Press Ctrl+D to exit Mininet CLI"
    echo ""
    cd "$SCRIPT_DIR"
    sudo python3 topo1.py
fi

echo ""
print_header "Setup Complete"
print_success "L4S topology is ready for NiCoLE experiments!"
echo ""
