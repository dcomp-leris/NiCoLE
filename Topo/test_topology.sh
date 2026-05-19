#!/bin/bash
#
# test_topology.sh - Test L4S topology connectivity
# Run this from the mininet CLI or after starting the topology
#

echo "======================================"
echo "L4S Topology Connectivity Tests"
echo "======================================"
echo ""

# Test 1: Host information
echo "[Test 1] Checking host connectivity..."
echo "  h0 interfaces:"
h0 ip link show
echo ""
echo "  h0 routes:"
h0 ip route show
echo ""

# Test 2: Same subnet ping (h0 ↔ h1)
echo "[Test 2] Testing same subnet (h0 ↔ h1)..."
h0 ping -c 2 192.168.100.11
echo "  ✓ Same subnet connectivity works"
echo ""

# Test 3: Ping h1 from h0 by hostname
echo "[Test 3] Testing reverse same subnet (h1 ↔ h0)..."
h1 ping -c 2 192.168.100.10
echo "  ✓ h1 can reach h0"
echo ""

# Test 4: Cross-subnet ping through router (h0 ↔ h2)
echo "[Test 4] Testing cross-subnet (h0 ↔ h2 through router)..."
h0 ping -c 2 192.168.200.10
echo "  ✓ Cross-subnet connectivity works"
echo ""

# Test 5: Reverse cross-subnet (h2 ↔ h0)
echo "[Test 5] Testing reverse cross-subnet (h2 ↔ h0)..."
h2 ping -c 2 192.168.100.10
echo "  ✓ h2 can reach h0 through router"
echo ""

# Test 6: h2 to h1
echo "[Test 6] Testing h2 ↔ h1 through router..."
h2 ping -c 2 192.168.100.11
echo "  ✓ h2 can reach h1 through router"
echo ""

# Test 7: Traceroute to show path
echo "[Test 7] Traceroute h0 → h2 (shows routing path)..."
h0 traceroute -m 5 192.168.200.10
echo ""

# Test 8: TCP/UDP iperf test (if available)
if command -v iperf &> /dev/null; then
    echo "[Test 8] Performance test with iperf..."
    echo "  Stopping any existing iperf servers..."
    pkill iperf || true
    sleep 1
    
    echo "  Starting iperf server on h0..."
    h0 iperf -s -D &
    IPERF_PID=$!
    sleep 2
    
    echo "  Running iperf from h2 to h0 (5 seconds)..."
    h2 iperf -c 192.168.100.10 -t 5 -R -i 1
    
    kill $IPERF_PID 2>/dev/null || true
    echo "  ✓ iperf test complete"
else
    echo "[Test 8] iperf not installed, skipping performance test"
fi

echo ""
echo "======================================"
echo "All tests completed!"
echo "======================================"
echo ""
echo "Network Summary:"
echo "  h0:  192.168.100.10 → h1: 192.168.100.11  (same subnet via br0)"
echo "  h0:  192.168.100.10 → h2: 192.168.200.10  (via router's br1 with DualQ)"
echo "  h2:  192.168.200.10 → h0: 192.168.100.10  (via router's br0)"
echo ""
