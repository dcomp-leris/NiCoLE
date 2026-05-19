#!/bin/bash
#
# validate_setup.sh - Validate L4S topology configuration
# Run this to verify everything is set up correctly before running mininet
#

set -e

echo "======================================"
echo "L4S Topology Setup Validator"
echo "======================================"
echo ""

ERRORS=0
WARNINGS=0

# Helper functions
check_command() {
    if command -v "$1" &> /dev/null; then
        echo "✓ $1 found"
        return 0
    else
        echo "✗ $1 NOT found"
        ((ERRORS++))
        return 1
    fi
}

check_file() {
    if [[ -f "$1" ]]; then
        echo "✓ $1 exists"
        return 0
    else
        echo "✗ $1 does NOT exist"
        ((ERRORS++))
        return 1
    fi
}

check_bridge() {
    if ip link show "$1" &> /dev/null; then
        echo "✓ Bridge $1 exists"
        return 0
    else
        echo "⚠ Bridge $1 does NOT exist (will be created by setup)"
        ((WARNINGS++))
        return 1
    fi
}

check_connectivity() {
    if ping -c 1 -W 2 "$1" &> /dev/null; then
        echo "✓ Can reach $1"
        return 0
    else
        echo "✗ Cannot reach $1"
        ((ERRORS++))
        return 1
    fi
}

# Section 1: Required Commands
echo "[1] Checking required commands..."
check_command "python3"
check_command "tc"
check_command "ip"
check_command "brctl"
check_command "ping"
echo ""

# Section 2: Required Files
echo "[2] Checking required files..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
check_file "$SCRIPT_DIR/topo1.py"
check_file "$SCRIPT_DIR/setup_topology.sh"
check_file "$SCRIPT_DIR/setup_router.sh"
check_file "$SCRIPT_DIR/test_topology.sh"
echo ""

# Section 3: Python modules
echo "[3] Checking Python modules..."
python3 -c "from mininet.net import Mininet" 2>/dev/null && echo "✓ mininet.net available" || (echo "✗ mininet NOT installed"; ((ERRORS++)))
python3 -c "from mininet.cli import CLI" 2>/dev/null && echo "✓ mininet.cli available" || (echo "✗ mininet CLI NOT available"; ((ERRORS++)))
echo ""

# Section 4: Router connectivity
echo "[4] Checking router connectivity..."
check_connectivity "192.168.100.2"
check_connectivity "192.168.200.2"
echo ""

# Section 5: Router verification
echo "[5] Checking router configuration..."
echo "Attempting to check DualQ on router (may fail if ssh not configured)..."
if ssh -o ConnectTimeout=2 root@192.168.100.2 "tc -s qdisc show dev enp8s0 | grep dualpi2" 2>/dev/null | grep -q dualpi2; then
    echo "✓ DualQ is active on router's enp8s0"
elif ssh -o ConnectTimeout=2 -u alireza 192.168.100.2 "tc -s qdisc show dev enp8s0 | grep dualpi2" 2>/dev/null | grep -q dualpi2; then
    echo "✓ DualQ is active on router's enp8s0"
else
    echo "⚠ Could not verify DualQ (may need manual check or ssh config)"
    ((WARNINGS++))
fi
echo ""

# Section 6: Bridges (if user is root)
echo "[6] Checking bridge status..."
if [[ $EUID -eq 0 ]]; then
    check_bridge "br0"
    check_bridge "br1"
else
    echo "⚠ Not running as root, skipping bridge checks"
    echo "   (Bridges will be created when setup_topology.sh is run with sudo)"
    ((WARNINGS++))
fi
echo ""

# Section 7: System settings
echo "[7] Checking system settings..."
if [[ $EUID -eq 0 ]]; then
    IP_FORWARD=$(sysctl -n net.ipv4.ip_forward 2>/dev/null || echo "unknown")
    if [[ "$IP_FORWARD" == "1" ]]; then
        echo "✓ IP forwarding is enabled"
    else
        echo "⚠ IP forwarding is disabled (will be enabled by setup_topology.sh)"
        ((WARNINGS++))
    fi
else
    echo "⚠ Not running as root, cannot check IP forwarding"
    ((WARNINGS++))
fi
echo ""

# Section 8: Network configuration
echo "[8] Checking network configuration..."
echo "Router addresses from host perspective:"
ip route | grep 192.168 || echo "  ⚠ No routes to 192.168.* subnets yet (expected)"
echo ""

# Section 9: Traffic control availability
echo "[9] Checking traffic control (tc) support..."
if tc qdisc show &> /dev/null; then
    echo "✓ Traffic control available"
    if tc qdisc add dev lo root dualpi2 2>&1 | grep -q "Unknown qdisc"; then
        echo "⚠ DualPI2 qdisc may not be available (check kernel)"
        ((WARNINGS++))
    else
        # Remove the test qdisc we just added
        tc qdisc del dev lo root 2>/dev/null || true
        echo "✓ DualPI2 qdisc available"
    fi
else
    echo "✗ Traffic control not available"
    ((ERRORS++))
fi
echo ""

# Section 10: Summary
echo "======================================"
echo "Validation Summary"
echo "======================================"
echo ""

if [[ $ERRORS -eq 0 ]]; then
    echo "✓ All critical checks passed!"
else
    echo "✗ Found $ERRORS critical error(s)"
fi

if [[ $WARNINGS -gt 0 ]]; then
    echo "⚠ Found $WARNINGS warning(s) - may need manual intervention"
fi

echo ""
echo "Next steps:"
if [[ $ERRORS -eq 0 ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "1. Run: sudo ./setup_topology.sh     (on host machine)"
        echo "2. Run: sudo python3 topo1.py        (to start topology)"
    else
        echo "1. Run: ./setup_topology.sh          (setup completed)"
        echo "2. Run: python3 topo1.py             (to start topology)"
    fi
else
    echo "Please fix the critical errors before proceeding."
fi
echo ""

# Exit with appropriate code
if [[ $ERRORS -gt 0 ]]; then
    exit 1
else
    exit 0
fi
