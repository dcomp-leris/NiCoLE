# L4S Topology Configuration Reference

## Network Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Host Machine                              │
│                                                               │
│  ┌──────────────┐        ┌──────────────┐                    │
│  │     h0       │        │     h1       │                    │
│  │192.168.100.10│        │192.168.100.11│                    │
│  └──────┬───────┘        └───────┬──────┘                    │
│         │                        │                           │
│         └────────┬───────────────┘                           │
│                  │                                            │
│            ┌─────▼─────┐                                     │
│            │   br0     │  (Linux Bridge)                     │
│            └─────┬─────┘                                     │
│                  │                                            │
│         veth pair│                                           │
│                  │                                            │
└──────────────────┼──────────────────────────────────────────┘
                   │
         Network   │  Connection
                   │
┌──────────────────┼──────────────────────────────────────────┐
│        ┌─────────▼─────────┐                                 │
│        │ enp7s0            │                                 │
│        │ 192.168.100.2/24  │                                 │
│        └─────────┬─────────┘                                 │
│                  │                                            │
│          L4S Router VM                                       │
│      (My-L4S-switch)                                         │
│                  │                                            │
│        ┌─────────▼─────────┐                                 │
│        │ enp8s0            │                                 │
│        │ 192.168.200.2/24  │                                 │
│        │ (DualQ Coupled)   │                                 │
│        └─────────┬─────────┘                                 │
│                  │                                            │
└──────────────────┼──────────────────────────────────────────┘
                   │
         Network   │  Connection
                   │
┌──────────────────┼──────────────────────────────────────────┐
│                  │                                            │
│            ┌─────▼─────┐                                     │
│            │   br1     │  (Linux Bridge)                     │
│            └─────┬─────┘                                     │
│                  │                                            │
│                  │                                            │
│         veth pair│                                           │
│                  │                                            │
│         ┌────────▼────────┐                                  │
│         │       h2        │                                  │
│         │ 192.168.200.10  │                                  │
│         │   (Client with  │                                  │
│         │   bottleneck)   │                                  │
│         └─────────────────┘                                  │
│                                                               │
│                    Host Machine                              │
└────────────────────────────────────────────────────────────┘
```

## IP Addressing

| Host | Interface | IP Address | Subnet | Notes |
|------|-----------|-----------|--------|-------|
| h0   | eth0      | 192.168.100.10/24 | Subnet 100 | Sender/Test host |
| h1   | eth0      | 192.168.100.11/24 | Subnet 100 | Sender/Test host |
| h2   | eth0      | 192.168.200.10/24 | Subnet 200 | Receiver (bottleneck) |
| Router | enp7s0  | 192.168.100.2/24  | Subnet 100 | Primary interface |
| Router | enp8s0  | 192.168.200.2/24  | Subnet 200 | DualQ interface |

## Bridge Configuration

### Bridge br0 (Subnet 100)
- **Connects**: h0, h1 to router's enp7s0
- **Members**: h0-eth0, h1-eth0, veth-br0-h
- **IP Range**: 192.168.100.0/24
- **Gateway**: 192.168.100.2 (router)

### Bridge br1 (Subnet 200)
- **Connects**: h2 to router's enp8s0
- **Members**: h2-eth0, veth-br1-h
- **IP Range**: 192.168.200.0/24
- **Gateway**: 192.168.200.2 (router)
- **Queue**: DualQ Coupled (for L4S priority handling)

## DualQ Configuration

Applied to router's enp8s0 interface:

```bash
qdisc dualpi2:
├── limit: 1000p (packet limit)
├── memlimit: 15000B (memory limit for buffering)
├── target: 16.7ms (typical RTT target)
├── tupdate: 16.7ms (update interval)
├── alpha: 0.160156 (proportional gain)
├── beta: 3.000000 (integral gain)
├── coupling_factor: 1 (couples L and C queues)
├── drop_on_overload: yes (drops excess packets)
├── drop_enqueue: yes (also on enqueue)
└── classic_protection: 1% (protects legacy TCP)
```

## Veth Pair Connections

### br0 Connection
- Host side: veth-br0-h (added to br0)
- Peer side: Used by br0 bridge logic
- Purpose: Connect h0, h1 to router's enp7s0

### br1 Connection
- Host side: veth-br1-h (added to br1)
- Peer side: Used by br1 bridge logic
- Purpose: Connect h2 to router's enp8s0 (with DualQ)

## Routing Paths

### h0 → h1 (Same Subnet)
```
h0 (192.168.100.10)
  ↓
h0-eth0 interface
  ↓
br0 bridge (local switching)
  ↓
h1-eth0 interface
  ↓
h1 (192.168.100.11)
```

### h0 → h2 (Cross Subnet through Router)
```
h0 (192.168.100.10)
  ↓
h0-eth0 → br0
  ↓
veth-br0-h → router enp7s0 (192.168.100.2)
  ↓
Router forwards (IP forwarding enabled)
  ↓
enp8s0 (192.168.200.2) with DualQ queue
  ↓
veth-br1-h → br1
  ↓
h2-eth0 → h2 (192.168.200.10)
```

### h2 → h0 (Reverse Path through Router)
```
h2 (192.168.200.10)
  ↓
h2-eth0 → br1
  ↓
veth-br1-h → router enp8s0 (192.168.200.2) with DualQ
  ↓
Router forwards (IP forwarding enabled)
  ↓
enp7s0 (192.168.100.2)
  ↓
veth-br0-h → br0
  ↓
h0-eth0 → h0 (192.168.100.10)
```

## Key Configuration Files

| File | Purpose |
|------|---------|
| topo1.py | Main Mininet topology definition |
| setup_topology.sh | Initialize bridges and veth on host |
| setup_router.sh | Verify router configuration |
| test_topology.sh | Run connectivity and performance tests |
| quick_start.sh | Guided setup with prerequisites check |
| README_L4S_SETUP.md | Comprehensive setup documentation |

## Common Commands

### Host Machine (Mininet Host)

```bash
# Check bridges
brctl show
ip link show type bridge

# View bridge members
bridge link show
ip link show master br0

# Check routing
h0 ip route show
h2 ip route show

# Test connectivity
h0 ping h1
h0 ping 192.168.200.10
h2 traceroute 192.168.100.10
```

### Router VM (L4S Router)

```bash
# Check interfaces
ifconfig
ip addr show

# Check routing
ip route show
sysctl net.ipv4.ip_forward

# Check DualQ
tc -s qdisc show dev enp8s0
tc -s class show dev enp8s0

# Monitor DualQ in real-time
watch -n 1 'tc -s qdisc show dev enp8s0'

# Check packet statistics
ethtool -S enp8s0
```

### Mininet CLI Commands

```bash
# Basic operations
mininet> h0 sh          # Shell on h0
mininet> h0 python3     # Python on h0
mininet> dump           # Show all host IPs

# Networking
mininet> h0 ifconfig
mininet> h0 ip route show
mininet> h0 netstat -rn

# Connectivity tests
mininet> h0 ping h1
mininet> h0 arping 192.168.100.2

# Performance testing
mininet> h0 iperf -s &
mininet> h2 iperf -c 192.168.100.10

# Packet capture
mininet> h0 tcpdump -i h0-eth0 -n icmp

# Debug routing
mininet> h0 traceroute 192.168.200.10
mininet> h0 mtr 192.168.200.10
```

## Troubleshooting Checklist

### Connectivity Issues

1. **h0/h1 cannot ping each other**
   - Check: `h0 ip link show`
   - Check: `brctl show br0`
   - Verify: h0-eth0 and h1-eth0 are in br0

2. **h0 cannot reach h2**
   - Check router IP forwarding: `My-L4S-switch# sysctl net.ipv4.ip_forward`
   - Check router routing: `My-L4S-switch# ip route show`
   - Test from router: `My-L4S-switch# ping 192.168.200.10`

3. **h2 cannot reach h0**
   - Check DualQ is working on router: `tc -s qdisc show dev enp8s0`
   - Verify QoS not blocking: Disable and retry

4. **Cannot reach router at all**
   - Check router VM is running
   - Check bridge connectivity: `brctl show`
   - Check veth pairs: `ip link | grep veth`

### Performance Issues

1. **Low throughput across router**
   - Check: tc qdisc doesn't have excessive drops
   - Monitor: `tc -s qdisc show dev enp8s0`
   - Increase memlimit if needed

2. **High latency**
   - Check: DualQ target/tupdate settings
   - Check: No kernel errors (dmesg)
   - Monitor: `watch -n 1 'tc -s qdisc show'`

## Performance Test Examples

### Basic throughput test
```bash
# Host 1: Server
mininet> h0 iperf -s

# Host 2: TCP client (generate traffic)
mininet> h2 iperf -c 192.168.100.10 -t 30 -i 5

# Monitor DualQ behavior
My-L4S-switch$ watch -n 1 'tc -s qdisc show dev enp8s0'
```

### ECN-enabled test (for L4S)
```bash
# Enable ECN on hosts
mininet> h2 sysctl -w net.ipv4.tcp_ecn=1

# Run test with ECN marking visible
mininet> h2 tcpdump -i h2-eth0 'tcp[tcpflags] & tcp-ce != 0'
```

### UDP test (for DualQ handling)
```bash
# Server on h0
mininet> h0 iperf -s -u

# Client from h2
mininet> h2 iperf -c 192.168.100.10 -u -b 10M -t 30
```

## Notes

- All hosts use DHCP-like configuration but with static IPs
- IP forwarding must be enabled on router for cross-subnet traffic
- DualQ applies priority-based queueing to enp8s0 (h2's link)
- h2 is the "bottleneck" - representing a slower last-mile link
- veth pairs are temporary and created by the setup scripts
- Bridges persist until manually deleted

