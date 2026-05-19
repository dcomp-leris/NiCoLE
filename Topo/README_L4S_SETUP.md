# L4S Router Topology Setup Guide

## Overview

This setup creates a Mininet topology where an external L4S Router VM (My-L4S-switch) acts as the router between three mininet hosts:
- **h0** & **h1**: Connected to 192.168.100.0/24 (via router's enp7s0)
- **h2**: Connected to 192.168.200.0/24 (via router's enp8s0 with DualQ)

```
Host Machine (Mininet)          Router VM (L4S)
┌─────────────────────┐         ┌──────────────────┐
│                     │         │                  │
│  h0 ─────┐          │         │ enp7s0           │
│          ├─→ br0 ───┼────────→│ 192.168.100.2    │
│  h1 ─────┘          │    veth │ (regular queue)  │
│                     │         │                  │
│  h2 ────────→ br1 ──┼────────→│ enp8s0           │
│                     │    veth │ 192.168.200.2    │
└─────────────────────┘         │ (DualQ Coupled)  │
                                │                  │
                                └──────────────────┘
```

## Prerequisites

- Mininet installed on host machine
- L4S Router VM (My-L4S-switch) running and accessible
- DualQ queue discipline applied on router's enp8s0
- Sudo/root access on both host and router

## Step-by-Step Setup

### 1. Prepare the Router VM

On the **router VM** (My-L4S-switch):

```bash
cd /path/to/NiCoLE/Topo
chmod +x setup_router.sh
sudo ./setup_router.sh
```

This will:
- Enable IP forwarding
- Verify network interfaces are configured
- Verify DualQ is active on enp8s0

### 2. Prepare the Host Machine

On the **host machine** where Mininet will run:

```bash
cd /path/to/NiCoLE/Topo
chmod +x setup_topology.sh
sudo ./setup_topology.sh
```

This will:
- Create bridges (br0, br1)
- Create veth pairs connecting to router
- Enable IP forwarding
- Verify router connectivity

### 3. Run the Topology

On the **host machine**:

```bash
cd /path/to/NiCoLE/Topo
sudo python3 topo1.py
```

You should see:
```
Network ready.

============================================================
L4S ROUTER TOPOLOGY READY
============================================================

Network Configuration:
  Subnet 1 (enp7s0): 192.168.100.0/24
    - h0: 192.168.100.10
    - h1: 192.168.100.11
    - Router: 192.168.100.2

  Subnet 2 (enp8s0): 192.168.200.0/24
    - h2: 192.168.200.10
    - Router: 192.168.200.2 (with DualQ)

Basic Tests:
  h0 ping h1              # Same subnet
  h0 ping 192.168.200.10  # Through router to h2
  h2 ping 192.168.100.10  # Through router to h0

Advanced Tests:
  h0 iperf -s             # Start server on h0
  h2 iperf -c 192.168.100.10 -t 30  # Connect from h2

mininet>
```

## Running Tests

### Option A: Manual Tests in Mininet CLI

```bash
# Same subnet connectivity
mininet> h0 ping -c 2 h1
mininet> h1 ping -c 2 h0

# Cross-subnet through router
mininet> h0 ping -c 2 192.168.200.10  (h0 → h2 through router)
mininet> h2 ping -c 2 192.168.100.10  (h2 → h0 through router)

# Traceroute to see the path
mininet> h0 traceroute 192.168.200.10

# View routing table
mininet> h0 ip route show
mininet> h2 ip route show

# Check network statistics
mininet> h0 netstat -rn

# DNS/reverse path
mininet> h0 hostname
mininet> h0 uname -a
```

### Option B: Automated Test Script

From another terminal:

```bash
cd /path/to/NiCoLE/Topo
chmod +x test_topology.sh
./test_topology.sh
```

This runs comprehensive connectivity tests.

## Performance Testing with DualQ

h2 is connected to the DualQ-equipped interface (enp8s0) on the router. To test the L4S queue behavior:

### Simple iperf test:

```bash
# Terminal 1: Start iperf server on h0
mininet> h0 iperf -s

# Terminal 2 (in mininet CLI): Start client on h2
mininet> h2 iperf -c 192.168.100.10 -t 30 -i 5

# View DualQ stats on router VM
My-L4S-switch# tc -s qdisc show dev enp8s0
```

### Advanced L4S testing:

```bash
# Check ECN capability
mininet> h2 ping -Q want 192.168.100.10

# Run netperf with different traffic classes
mininet> h2 netperf -H 192.168.100.10 -l 30 -- -R cp

# Monitor DualQ on router
My-L4S-switch# watch -n 1 'tc -s qdisc show dev enp8s0'
```

## Network Configuration Details

### Bridges Configuration

- **br0**: Acts as local switch for h0, h1
  - Connected to router via veth pair
  - Routes to 192.168.100.0/24
  
- **br1**: Acts as local switch for h2
  - Connected to router via veth pair  
  - Routes to 192.168.200.0/24
  - Traffic passes through DualQ on router's enp8s0

### Routing

- **h0, h1**: Default route → 192.168.100.2 (router's enp7s0)
- **h2**: Default route → 192.168.200.2 (router's enp8s0)

### DualQ Configuration on Router

From your setup output:
```
qdisc dualpi2 8001: root refcnt 2 limit 1000p memlimit 15000B 
  target 16.7ms tupdate 16.7ms alpha 0.160156 beta 3.000000 
  coupling_factor 1 drop_on_overload drop_enqueue classic_protection 1%
```

- **target**: 16.7ms (typical RTT)
- **memlimit**: 15KB (prevents excessive buffering)
- **coupling_factor**: 1 (L and C queues coupled)
- **classic_protection**: 1% (protects legacy TCP)

## Troubleshooting

### Issue: Cannot reach router from h0/h1

```bash
# Check on host machine
ip link show br0
bridge link show
ping -c 1 192.168.100.2

# Check on router
ifconfig enp7s0
```

### Issue: h0 cannot reach h2

```bash
# Verify router has IP forwarding enabled
My-L4S-switch# sysctl net.ipv4.ip_forward

# Check routes on router
My-L4S-switch# ip route show

# Ping from router
My-L4S-switch# ping 192.168.200.10
My-L4S-switch# ping 192.168.100.10
```

### Issue: DualQ not engaged

```bash
# On router, verify DualQ is loaded and applied
My-L4S-switch# tc -s qdisc show dev enp8s0
My-L4S-switch# modprobe sch_dualpi2

# Reapply if needed
My-L4S-switch# ./setup_dualq_coupling.sh
```

### Issue: Bridges not showing in brctl

```bash
# Check with ip link
ip link show type bridge

# Manually verify
ip link show br0
ip link show br1
```

## Advanced Configurations

### Enable ECN on all hosts

```bash
# In mininet CLI
mininet> h0 sysctl -w net.ipv4.tcp_ecn=1
mininet> h1 sysctl -w net.ipv4.tcp_ecn=1
mininet> h2 sysctl -w net.ipv4.tcp_ecn=1
```

### Increase DualQ memory for higher throughput

```bash
# On router
My-L4S-switch# tc qdisc replace root dev enp8s0 dualpi2 memlimit 30000B
```

### Fine-tune alpha/beta for different RTT conditions

See your router's `setup_dualq_coupling.sh` script for parameter tuning.

## Cleanup

### Stop Mininet gracefully

```bash
mininet> exit
```

### Clean up bridges (if needed)

```bash
sudo ip link del br0
sudo ip link del br1
```

### Reset router to defaults

```bash
My-L4S-switch# sudo ip link del veth-br0-r
My-L4S-switch# sudo ip link del veth-br1-r
```

## Files in This Setup

- `topo1.py` - Main topology definition with L4S router integration
- `setup_router.sh` - Configure the L4S router VM
- `setup_topology.sh` - Prepare host machine with bridges
- `test_topology.sh` - Automated connectivity tests
- `README_L4S_SETUP.md` - This file

## Quick Start Checklist

- [ ] L4S Router VM is running (My-L4S-switch)
- [ ] DualQ is applied to enp8s0 on router
- [ ] Run `sudo ./setup_router.sh` on router
- [ ] Run `sudo ./setup_topology.sh` on host  
- [ ] Run `sudo python3 topo1.py` on host
- [ ] Verify with `h0 ping h1` in Mininet CLI
- [ ] Verify with `h0 ping 192.168.200.10` for cross-subnet
- [ ] Run performance tests with iperf

## References

- Mininet: http://mininet.org/
- L4S (Low Latency Low Loss Scalable Throughput): https://www.ietf.org/wg/l4s/
- DualQ Coupled Queue: https://tools.ietf.org/html/draft-briscoe-docsis-l4s-dualq
- Linux Traffic Control: https://man7.org/linux/man-pages/man8/tc.8.html

