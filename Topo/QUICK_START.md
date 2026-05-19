# Quick Start Guide - L4S Topology with NiCoLE

## TL;DR - 3 Step Setup

### Step 1: On Router VM (My-L4S-switch)
```bash
ssh user@router-ip  # Or access the VM

cd /path/to/NiCoLE/Topo
chmod +x setup_router.sh
sudo ./setup_router.sh

# Verify DualQ is active
tc -s qdisc show dev enp8s0
```

### Step 2: On Host Machine (where Mininet runs)
```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo ./setup_topology.sh
```

### Step 3: Run Topology
```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo python3 topo1.py
```

---

## Basic Tests (in Mininet CLI)

```bash
mininet> h0 ping h1
mininet> h0 ping 192.168.200.10
mininet> h2 ping 192.168.100.10
mininet> h0 traceroute 192.168.200.10
```

---

## File Descriptions

| File | Command | Purpose |
|------|---------|---------|
| `topo1.py` | `sudo python3 topo1.py` | Main topology, run this to start |
| `quick_start.sh` | `./quick_start.sh` | Guided setup (recommended first time) |
| `setup_topology.sh` | `sudo ./setup_topology.sh` | Manual setup on host |
| `setup_router.sh` | `sudo ./setup_router.sh` | Manual setup on router VM |
| `test_topology.sh` | `./test_topology.sh` | Automated connectivity tests |
| `README_L4S_SETUP.md` | - | Full documentation |
| `CONFIG_REFERENCE.md` | - | Network architecture details |

---

## Network Layout

```
Host Side          L4S Router         Host Side
Subnet 100:        (with DualQ):      Subnet 200:
h0, h1             192.168.100.2      h2
                   ↕                  ↕
                   192.168.200.2      
  ┌──br0──┐        ┌─────────┐       ┌──br1──┐
  │ h0    │        │ enp7s0  │       │       │
  │ h1    │───────→│ Router  │───────→│ h2    │
  └─────────┘       │ enp8s0  │       └─────────┘
                    │ (DualQ) │       
                    └─────────┘
```

---

## Network Configuration

| Item | Config |
|------|--------|
| h0 IP | 192.168.100.10/24, gateway 192.168.100.2 |
| h1 IP | 192.168.100.11/24, gateway 192.168.100.2 |
| h2 IP | 192.168.200.10/24, gateway 192.168.200.2 |
| Router enp7s0 | 192.168.100.2/24 |
| Router enp8s0 | 192.168.200.2/24 (with DualQ) |
| DualQ target | 16.7ms (RTT) |
| DualQ memlimit | 15KB |

---

## Performance Testing

### Simple iperf test:
```bash
# Terminal 1 - On host, start mininet and run server
mininet> h0 iperf -s

# Terminal 2 - In mininet CLI, run client
mininet> h2 iperf -c 192.168.100.10 -t 30 -R

# Terminal 3 - On router, monitor DualQ
My-L4S-switch# watch -n 1 'tc -s qdisc show dev enp8s0'
```

### Monitor DualQ statistics:
```bash
My-L4S-switch# tc -s qdisc show dev enp8s0
My-L4S-switch# tc -s class show dev enp8s0
```

---

## Troubleshooting

### "Cannot reach router"
```bash
# On host:
ping 192.168.100.2
ping 192.168.200.2

# On router:
ifconfig enp7s0 enp8s0
sysctl net.ipv4.ip_forward
```

### "h0/h1 cannot ping each other"
```bash
# Check bridges created correctly
sudo brctl show
sudo ip link show type bridge

# Rerun setup:
sudo ./setup_topology.sh
```

### "h2 cannot reach h0 through router"
```bash
# Verify routing on router
My-L4S-switch# ip route show

# Verify IP forwarding
My-L4S-switch# sysctl net.ipv4.ip_forward

# Verify DualQ is active
My-L4S-switch# tc -s qdisc show dev enp8s0
```

---

## Advanced Testing

### ECN with L4S:
```bash
mininet> h2 sysctl -w net.ipv4.tcp_ecn=1
mininet> h2 iperf -c 192.168.100.10 -t 30
```

### View live DualQ metrics:
```bash
# On router, shows buffer depth and traffic classification
My-L4S-switch# watch -n 0.5 'tc -s qdisc show dev enp8s0'
```

### Packet capture through DualQ:
```bash
# Capture on h2
mininet> h2 tcpdump -i h2-eth0 -n 'host 192.168.100.10'

# Capture on router to see DualQ behavior
My-L4S-switch# tcpdump -i enp8s0 -n -A 'host 192.168.100.10'
```

---

## Cleanup

```bash
# Stop mininet (Ctrl+D in mininet CLI)
mininet> exit

# Optional: Remove bridges
sudo ip link del br0
sudo ip link del br1

# Optional: Check what's left
sudo brctl show
sudo ip link show type bridge
```

---

## Typical Workflow

1. **Initial Setup**
   ```bash
   # Run once to set everything up
   ./quick_start.sh
   ```

2. **Daily Startup**
   ```bash
   # Just run the topology
   sudo python3 topo1.py
   ```

3. **Testing**
   ```bash
   # In mininet CLI
   mininet> h0 ping h1          # Basic test
   mininet> h0 iperf -s &       # Start server
   mininet> h2 iperf -c 192.168.100.10 -t 30  # Client
   ```

4. **Monitoring**
   ```bash
   # On another terminal, on router
   My-L4S-switch# watch -n 1 'tc -s qdisc show dev enp8s0'
   ```

5. **Cleanup**
   ```bash
   # Stop with Ctrl+D in mininet CLI
   ```

---

## Files on Disk

After setup, you'll have:

```
/home/alireza/Myprojects/NiCoLE/Topo/
├── topo1.py                      ← Main topology (run this!)
├── setup_topology.sh             ← Host setup
├── setup_router.sh               ← Router setup
├── test_topology.sh              ← Test suite
├── quick_start.sh                ← Guided setup
├── README_L4S_SETUP.md           ← Full documentation
├── CONFIG_REFERENCE.md           ← Network architecture
└── QUICK_START.md                ← This file
```

---

## Support

Refer to:
- `README_L4S_SETUP.md` - Full setup guide
- `CONFIG_REFERENCE.md` - Network architecture
- `setup_router.sh` - Router initialization
- `setup_topology.sh` - Topology initialization

For L4S theory:
- https://www.ietf.org/wg/l4s/
- https://tools.ietf.org/html/draft-briscoe-docsis-l4s-dualq

---

## Quick Checklist

- [ ] Router VM (My-L4S-switch) is running
- [ ] Can ping router from host (192.168.100.2 and 192.168.200.2)
- [ ] Ran `sudo ./setup_router.sh` on router
- [ ] Ran `sudo ./setup_topology.sh` on host
- [ ] DualQ is active on router's enp8s0
- [ ] Ready to run `sudo python3 topo1.py`

---

**Created**: May 19, 2026  
**For**: NiCoLE Project  
**Topology**: h0, h1 (192.168.100.0/24) ↔ L4S Router ↔ h2 (192.168.200.0/24 with DualQ)

