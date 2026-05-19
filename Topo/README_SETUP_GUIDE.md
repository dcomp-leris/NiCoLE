# L4S Router Topology for NiCoLE - Complete Setup Guide

## 📋 Overview

This setup creates a Mininet-based network topology integrated with an external **L4S (Low Latency, Low Loss, Scalable Throughput) Router VM** equipped with **DualQ Coupled Queue** for advanced QoS testing.

### Network Topology

```
┌─────────────────────────────────┐   ┌──────────────────────────┐
│  Mininet on Host                │   │  L4S Router VM           │
│                                 │   │  (My-L4S-switch)         │
│  h0 (192.168.100.10)        ────┼───┼─→ enp7s0 (192.168.100.2) │
│  h1 (192.168.100.11)        ────┼───┼─→ [regular queue]        │
│                                 │   │                          │
│  h2 (192.168.200.10) ───────────┼───┼─→ enp8s0 (192.168.200.2) │
│  [bottleneck client]            │   │   [DualQ Coupled Queue]  │
│                                 │   │                          │
└─────────────────────────────────┘   └──────────────────────────┘
```

---

## 🚀 Quick Start (3 Steps)

### Step 1️⃣ On Router VM

```bash
cd /path/to/NiCoLE/Topo
sudo ./setup_router.sh
```

Verify DualQ is active:
```bash
tc -s qdisc show dev enp8s0  # Should show "dualpi2"
```

### Step 2️⃣ On Host Machine (where Mininet runs)

```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo ./setup_topology.sh
```

### Step 3️⃣ Run Topology

```bash
sudo python3 topo1.py
```

Then in the Mininet CLI, test:
```bash
mininet> h0 ping h1                 # Same subnet
mininet> h0 ping 192.168.200.10     # Cross subnet to h2
mininet> h2 ping 192.168.100.10     # Reverse path
```

---

## 📁 File Structure & Purpose

```
NiCoLE/Topo/
├── topo1.py                    ← ⭐ MAIN TOPOLOGY - Run this!
├── setup_topology.sh           ← Initialize host machine
├── setup_router.sh             ← Initialize router VM  
├── test_topology.sh            ← Automated tests
├── validate_setup.sh           ← Pre-flight check
├── quick_start.sh              ← Guided setup
├── QUICK_START.md              ← This quick reference
├── README_L4S_SETUP.md         ← Comprehensive guide
└── CONFIG_REFERENCE.md         ← Network architecture
```

### What Each File Does

| File | Purpose | When to Use |
|------|---------|-----------|
| `topo1.py` | **Main topology** | `sudo python3 topo1.py` after setup |
| `quick_start.sh` | Guided step-by-step setup | First time setup? Use this |
| `setup_topology.sh` | Configure host machine | Manually setup host side |
| `setup_router.sh` | Configure router VM | Manually setup router side |
| `test_topology.sh` | Run connectivity tests | Verify topology works |
| `validate_setup.sh` | Pre-flight validation | Before running topo1.py |
| `QUICK_START.md` | Quick reference | Quick lookup |
| `README_L4S_SETUP.md` | Full documentation | Detailed troubleshooting |
| `CONFIG_REFERENCE.md` | Network architecture | Understanding topology |

---

## 🔧 Setup Methods

### Method A: Automatic (Recommended for First Time)

```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
./quick_start.sh
```

The script will:
- ✓ Check prerequisites
- ✓ Verify router connectivity
- ✓ Create bridges on host
- ✓ Optionally start topology

### Method B: Step-by-Step (Manual)

**On Router VM:**
```bash
sudo ./setup_router.sh
```

**On Host Machine:**
```bash
sudo ./setup_topology.sh
```

**Start Topology:**
```bash
sudo python3 topo1.py
```

### Method C: Verify Before Starting (Recommended)

```bash
# Check everything is ready
./validate_setup.sh

# If all green, start topology
sudo python3 topo1.py
```

---

## 🧪 Testing the Topology

### In Mininet CLI (Basic Tests)

```bash
# Same subnet test (h0 ↔ h1)
mininet> h0 ping h1

# Cross subnet via router (h0 ↔ h2)
mininet> h0 ping 192.168.200.10

# Reverse path (h2 ↔ h0)
mininet> h2 ping 192.168.100.10

# View routing
mininet> h0 ip route
mininet> h2 ip route

# Traceroute shows path
mininet> h0 traceroute 192.168.200.10
```

### Automated Tests

```bash
# In a separate terminal, run test suite
./test_topology.sh
```

### Performance Test with iperf

```bash
# Terminal 1: Start server on h0
mininet> h0 iperf -s

# Terminal 2: Run client from h2 to h0
mininet> h2 iperf -c 192.168.100.10 -t 30 -R

# Terminal 3: Monitor DualQ on router
# (on router VM)
watch -n 1 'tc -s qdisc show dev enp8s0'
```

---

## 🌐 Network Configuration

### IP Addresses

| Host | IP | Subnet | Notes |
|------|----|----|-------|
| h0   | 192.168.100.10/24 | Subnet 100 | Can reach h1 directly, h2 via router |
| h1   | 192.168.100.11/24 | Subnet 100 | Receiver for same-subnet tests |
| h2   | 192.168.200.10/24 | Subnet 200 | Bottleneck client connected to DualQ |
| Router (enp7s0) | 192.168.100.2/24 | Subnet 100 | Gateway for h0, h1 |
| Router (enp8s0) | 192.168.200.2/24 | Subnet 200 | Gateway for h2 (with DualQ) |

### Bridges

- **br0**: Local bridge for h0, h1 → connects to router's enp7s0
- **br1**: Local bridge for h2 → connects to router's enp8s0 (with DualQ)

### DualQ Configuration on enp8s0

```
target: 16.7ms (typical RTT)
tupdate: 16.7ms (update interval)
memlimit: 15KB (buffer limit)
coupling_factor: 1 (couples L and C queues)
classic_protection: 1% (protects legacy TCP)
```

---

## 📊 DualQ and L4S

The topology uses **DualQ Coupled Queue** on the router's enp8s0 interface:

- **h0, h1**: Send traffic through standard queue (enp7s0)
- **h2**: Receives traffic through priority-aware L4S queue (enp8s0)
- **DualQ**: Provides low latency for ECN-capable flows, classic protection for legacy TCP

### L4S Benefits

✅ **Low Latency**: ~16.7ms target  
✅ **High Throughput**: Scalable bandwidth utilization  
✅ **Low Loss**: ECN-based congestion feedback  
✅ **Backward Compatible**: Works with legacy TCP via classic protection  

---

## 🐛 Troubleshooting

### Can't connect to router

```bash
# Check router is reachable
ping 192.168.100.2
ping 192.168.200.2

# On router, verify interfaces are up
ifconfig enp7s0 enp8s0
```

### h0/h1 cannot ping each other

```bash
# Verify bridge was created
brctl show
ip link show br0

# Check routing
h0 ip route
```

### h2 cannot reach h0 through router

```bash
# Check IP forwarding on router
sysctl net.ipv4.ip_forward  # Should be 1

# Verify DualQ is active
tc -s qdisc show dev enp8s0  # Should show dualpi2

# Test from router to both subnets
ping 192.168.100.10  # h0
ping 192.168.200.10  # h2
```

### Low iperf throughput

```bash
# Check DualQ not dropping packets
tc -s qdisc show dev enp8s0  # Look for drops

# Increase buffer if needed
tc qdisc replace root dev enp8s0 dualpi2 memlimit 30000B

# Check both hosts have sufficient bandwidth
h0 ethtool -S <interface>
```

### Bridges don't persist after reboot

Bridges are created dynamically by the setup scripts. After reboot:
```bash
sudo ./setup_topology.sh  # Recreate bridges
```

To make persistent:
- Configure network interfaces in `/etc/network/interfaces` or netplan
- Or add bridge setup to startup scripts

---

## 📝 Common Commands Reference

### View Network Status

```bash
# On host
brctl show                    # Show all bridges
ip link show                  # Show network interfaces
ip route show                 # Show routing table

# In Mininet
mininet> dump                 # Show all host configs
mininet> h0 ifconfig          # Host network config
mininet> h0 ip route show     # Host routing
```

### Monitor DualQ

```bash
# On router - one-time view
tc -s qdisc show dev enp8s0

# On router - continuous monitoring
watch -n 1 'tc -s qdisc show dev enp8s0'
watch -n 0.5 'tc -s qdisc show dev enp8s0'

# Detailed stats
tc -s class show dev enp8s0
```

### Performance Testing

```bash
# iPerf - TCP throughput
mininet> h0 iperf -s              # Server
mininet> h2 iperf -c 192.168.100.10 -t 30 -R

# iPerf - UDP bandwidth
mininet> h0 iperf -s -u           # Server
mininet> h2 iperf -c 192.168.100.10 -u -b 10M -t 30

# netperf - More detailed metrics
mininet> h0 netperf -s
mininet> h2 netperf -H 192.168.100.10

# Packet capture
mininet> h2 tcpdump -i h2-eth0 'host 192.168.100.10'
```

### Clean Up

```bash
# From Mininet CLI
mininet> exit              # Graceful shutdown

# Or from terminal
sudo pkill -f mininet
sudo pkill -f python3.*topo

# Remove bridges (optional)
sudo ip link del br0
sudo ip link del br1

# Check what's left
brctl show
```

---

## 📚 Quick Tips

1. **Always run as root/sudo**: Mininet network operations require elevated privileges

2. **DualQ monitoring tip**: Run this in a separate terminal for real-time DualQ metrics:
   ```bash
   My-L4S-switch$ watch -n 0.5 'tc -s qdisc show dev enp8s0'
   ```

3. **Exit Mininet properly**: Use `Ctrl+D` or `exit` in mininet CLI to clean up resources

4. **Enable ECN for L4S**: In mininet CLI:
   ```bash
   mininet> h0 sysctl -w net.ipv4.tcp_ecn=1
   mininet> h2 sysctl -w net.ipv4.tcp_ecn=1
   ```

5. **Check router routing**: If packets aren't reaching across subnets:
   ```bash
   My-L4S-switch# ip route show
   My-L4S-switch# sysctl net.ipv4.ip_forward
   ```

---

## 🔄 Workflow Example

### Day 1: Initial Setup

```bash
# Check prerequisites
./validate_setup.sh

# Run guided setup
./quick_start.sh

# Should automatically start topology if all checks pass
```

### Day 2+: Daily Usage

```bash
# Just run the topology
sudo python3 topo1.py

# In Mininet CLI, run your tests
mininet> h0 iperf -s &
mininet> h2 iperf -c 192.168.100.10 -t 30 -R

# Exit gracefully
mininet> exit
```

---

## 📞 Getting Help

1. **Check file**: [README_L4S_SETUP.md](README_L4S_SETUP.md) - Full documentation
2. **Architecture**: [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) - Network details
3. **Quick ref**: [QUICK_START.md](QUICK_START.md) - Quick lookup
4. **Validate**: Run `./validate_setup.sh` to check setup

---

## 📝 Files Created/Modified

All files are in: `/home/alireza/Myprojects/NiCoLE/Topo/`

- ✅ `topo1.py` - Updated with L4S router support
- ✅ `setup_topology.sh` - New helper script
- ✅ `setup_router.sh` - New helper script
- ✅ `test_topology.sh` - New test suite
- ✅ `quick_start.sh` - New guided setup
- ✅ `validate_setup.sh` - New validator
- ✅ `README_L4S_SETUP.md` - New full docs
- ✅ `CONFIG_REFERENCE.md` - New architecture docs
- ✅ `QUICK_START.md` - New quick ref
- ✅ `README_SETUP_GUIDE.md` - This file

---

## ✅ Setup Checklist

Before running topology:

- [ ] L4S Router VM (My-L4S-switch) is running
- [ ] Can ping router from host: `ping 192.168.100.2` ✓
- [ ] Router has DualQ on enp8s0: `tc qdisc show dev enp8s0` shows dualpi2 ✓
- [ ] Ran `sudo ./setup_router.sh` on router ✓
- [ ] Ran `sudo ./setup_topology.sh` on host ✓
- [ ] Mininet is installed: `which mn` ✓
- [ ] Python3 and dependencies available ✓
- [ ] Have sudo/root access on both machines ✓

Ready to run: `sudo python3 topo1.py` ✅

---

**Setup completed**: May 19, 2026  
**For**: NiCoLE Project with L4S Router VM integration  
**Topology**: 3 hosts, 2 subnets, 1 DualQ-enabled router

