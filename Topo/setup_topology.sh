#!/bin/bash
#
# setup_topology.sh - Setup L4S topology on host machine
# Run this on the host machine where mininet will run
# Requires: sudo privileges
#

set -e

ROUTER_IP_100="192.168.100.2"
ROUTER_IP_200="192.168.200.2"
BRIDGE_0="mnbr0"
BRIDGE_1="mnbr1"
ROUTER_TAP_100="vnet1"
ROUTER_TAP_200="vnet2"
BRIDGE_IP_100="192.168.100.1/24"
BRIDGE_IP_200="192.168.200.1/24"

echo "======================================"
echo "L4S Topology Setup"
echo "======================================"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root"
    sudo "$0" "$@"
    exit $?
fi

# Step 1: Create bridges
echo "[Step 1] Creating bridges..."
for br in $BRIDGE_0 $BRIDGE_1; do
    if ip link show $br &> /dev/null; then
        echo "  Bridge $br already exists, removing old one..."
        ip link set $br down 2>/dev/null || true
        ip link del $br &>/dev/null || true
    fi
    echo "  Creating $br..."
    ip link add $br type bridge
    if [[ "$br" == "$BRIDGE_0" ]]; then
        ip addr add ${BRIDGE_IP_100} dev $BRIDGE_0
    else
        ip addr add ${BRIDGE_IP_200} dev $BRIDGE_1
    fi
    ip link set $br up
done

# Step 2: Attach router VM tap interfaces to bridges
echo "[Step 2] Attaching router VM taps to bridges..."

if ip link show $ROUTER_TAP_100 &> /dev/null; then
    echo "  Attaching $ROUTER_TAP_100 to $BRIDGE_0"
    ip link set $ROUTER_TAP_100 up
    ip link set $ROUTER_TAP_100 master $BRIDGE_0
else
    echo "  ✗ Router tap $ROUTER_TAP_100 not found"
    echo "    Expecting the VM tap interface for router subnet 192.168.100.0/24"
    exit 1
fi

if ip link show $ROUTER_TAP_200 &> /dev/null; then
    echo "  Attaching $ROUTER_TAP_200 to $BRIDGE_1"
    ip link set $ROUTER_TAP_200 up
    ip link set $ROUTER_TAP_200 master $BRIDGE_1
else
    echo "  ✗ Router tap $ROUTER_TAP_200 not found"
    echo "    Expecting the VM tap interface for router subnet 192.168.200.0/24"
    exit 1
fi

# Step 3: Check router connectivity
echo "[Step 3] Checking router connectivity..."
if ping -c 1 -W 2 $ROUTER_IP_100 &> /dev/null; then
    echo "  ✓ Can reach router at $ROUTER_IP_100"
else
    echo "  ✗ Cannot reach router at $ROUTER_IP_100"
    echo "  Make sure the router VM is configured with 192.168.100.2 and the VM interface is up"
    exit 1
fi

if ping -c 1 -W 2 $ROUTER_IP_200 &> /dev/null; then
    echo "  ✓ Can reach router at $ROUTER_IP_200"
else
    echo "  ✗ Cannot reach router at $ROUTER_IP_200"
    echo "  Make sure the router VM is configured with 192.168.200.2 and the VM interface is up"
    exit 1
fi

# Step 4: Confirm bridge routes
echo "[Step 4] Setting up bridge connectivity..."
ip route replace 192.168.100.0/24 dev $BRIDGE_0 proto kernel scope link 2>/dev/null || true
ip route replace 192.168.200.0/24 dev $BRIDGE_1 proto kernel scope link 2>/dev/null || true

# Step 5: Enable IP forwarding on host
echo "[Step 5] Enabling IP forwarding on host..."
sysctl -w net.ipv4.ip_forward=1 > /dev/null

# Step 6: Verify setup
echo ""
echo "[Step 6] Verifying setup..."
echo "  Bridges:"
for br in $BRIDGE_0 $BRIDGE_1; do
    echo "    $br: $(ip link show $br | grep -oP '(?<=<).*?(?=>)')"
done

echo ""
echo "  Bridge members:"
brctl show 2>/dev/null || bridge link show | grep -E "^(veth|br|vnet)"

echo ""
echo "======================================"
echo "Topology setup complete!"
echo "======================================"
echo ""
echo "Ready to run: sudo python3 topo1.py"
echo ""
