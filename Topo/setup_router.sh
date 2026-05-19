#!/bin/bash
#
# setup_router.sh - Configure the L4S Router VM
# Run this on the router VM (My-L4S-switch)
#

set -e

ROUTER_HOSTNAME="My-L4S-switch"

echo "======================================"
echo "L4S Router Configuration"
echo "======================================"
echo ""

# Check if we're on the router
if [[ $(hostname) != $ROUTER_HOSTNAME ]]; then
    echo "WARNING: Current hostname is $(hostname), expected $ROUTER_HOSTNAME"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Enable IP forwarding
echo "[Step 1] Enabling IP forwarding..."
sudo sysctl -w net.ipv4.ip_forward=1
sudo bash -c 'echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf 2>/dev/null || true'

# Configure interfaces (should already be up, just verify)
echo "[Step 2] Verifying network interfaces..."
echo "  enp7s0 (Subnet 100): $(ip -4 addr show enp7s0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')"
echo "  enp8s0 (Subnet 200): $(ip -4 addr show enp8s0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')"

# Verify DualQ on enp8s0
echo "[Step 3] Verifying DualQ queue on enp8s0..."
if tc -s qdisc show dev enp8s0 | grep -q "dualpi2"; then
    echo "  ✓ DualQ is active on enp8s0"
    tc -s qdisc show dev enp8s0
else
    echo "  ✗ WARNING: DualQ not found on enp8s0"
    echo "  Apply DualQ with: ./setup_dualq_coupling.sh"
fi

# Test routing
echo ""
echo "[Step 4] Testing routing configuration..."
echo "  Route table:"
ip route show
echo ""

echo "======================================"
echo "Router setup complete!"
echo "======================================"
echo ""
echo "Router is ready to route between:"
echo "  - 192.168.100.0/24 (enp7s0)"
echo "  - 192.168.200.0/24 (enp8s0 with DualQ)"
echo ""
