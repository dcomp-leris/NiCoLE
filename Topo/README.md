# 🚀 L4S Router Topology - Start Here!

Welcome! This is your complete setup for running Mininet topology with an external L4S Router VM.

---

## 📖 Choose Your Path

### 🎯 **First Time? Start Here**
→ Read: [README_SETUP_GUIDE.md](README_SETUP_GUIDE.md) (Complete guide)  
→ Then run: `./quick_start.sh` (Guided setup)

### ⚡ **Quick Start (Experienced Users)**
→ Read: [QUICK_START.md](QUICK_START.md) (TL;DR version)  
→ Then run topology: `sudo python3 topo1.py`

### 🔍 **Detailed Information Needed**
→ Architecture: [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) (Network details)  
→ Full docs: [README_L4S_SETUP.md](README_L4S_SETUP.md) (Comprehensive guide)  
→ Troubleshooting: See those docs' troubleshooting sections

### ✅ **Validate Setup**
→ Run: `./validate_setup.sh` (Pre-flight check)  
→ Then proceed to run topology

---

## 📁 Files Overview

### 🔴 **CRITICAL - Must Run**

```bash
# 1. Start topology (main program)
sudo python3 topo1.py

# 2. Setup helpers (run once per machine)
sudo ./setup_topology.sh      # On host machine
sudo ./setup_router.sh        # On router VM
```

### 🟡 **HELPFUL - Improvement**

```bash
# Pre-flight validation
./validate_setup.sh

# Guided setup (first time)
./quick_start.sh

# Tests and verification
./test_topology.sh
```

### 🟢 **REFERENCE - For Learning**

```
QUICK_START.md              ← Quick reference (3 pages)
README_SETUP_GUIDE.md       ← Complete guide (5 pages)
README_L4S_SETUP.md         ← Advanced guide (8 pages)
CONFIG_REFERENCE.md         ← Architecture details (12 pages)
```

---

## 🎯 Quick Workflow

### **Setup (Do Once)**

```bash
# 1. On Router VM (My-L4S-switch):
sudo ./setup_router.sh

# 2. On Host Machine:
sudo ./setup_topology.sh

# 3. Verify:
./validate_setup.sh
```

### **Run (Every Time)**

```bash
# On Host Machine:
sudo python3 topo1.py

# In Mininet CLI:
mininet> h0 ping h1
mininet> h0 ping 192.168.200.10
mininet> h2 ping 192.168.100.10
```

### **Test (Optional)**

```bash
# In another terminal:
./test_topology.sh

# Or manually:
mininet> h0 iperf -s &
mininet> h2 iperf -c 192.168.100.10
```

---

## 🌐 Network at a Glance

```
h0 (192.168.100.10)  ─┬─ Subnet 100 ─┬─ Router enp7s0 (192.168.100.2)
h1 (192.168.100.11)  ─┘              │  [Standard Queue]
                                      │
                      ┌───────────────┤
                      │               │
                      │          Router enp8s0 (192.168.200.2)
                      │          [DualQ Coupled Queue]
                      │               │
                      └───────────────┘
                                      │
h2 (192.168.200.10) ──── Subnet 200 ──

h2 connects to DualQ interface (bottleneck point)
```

---

## ❓ Common Questions

### Q: Where do I start?
**A:** Run `./quick_start.sh` - it will guide you through everything

### Q: How do I run the topology?
**A:** `sudo python3 topo1.py` after setup is complete

### Q: How do I test it?
**A:** In Mininet CLI: `h0 ping h1` and `h0 ping 192.168.200.10`

### Q: What's DualQ?
**A:** Advanced queue discipline on router's enp8s0 interface that prioritizes L4S flows

### Q: Is the topology persistent?
**A:** Only while Mininet is running. Bridges are recreated on each setup

### Q: Do I need both machines?
**A:** Yes - Mininet on host machine, L4S Router VM on separate machine

---

## 🔧 Minimal Setup (For Those in a Hurry)

```bash
# Step 1: On router - verify DualQ is active
My-L4S-switch$ tc -s qdisc show dev enp8s0

# Step 2: On host - setup topology
host$ sudo ./setup_topology.sh

# Step 3: Run topology
host$ sudo python3 topo1.py

# Step 4: Test in Mininet CLI
mininet> h0 ping h1
mininet> exit
```

**Total time**: ~2 minutes

---

## 📊 File Sizes & Purposes

| File | Size | Purpose |
|------|------|---------|
| `topo1.py` | 3.0K | ⭐ **Main topology** - Run this! |
| `setup_topology.sh` | 3.3K | Initialize host machine |
| `setup_router.sh` | 1.8K | Initialize router VM |
| `test_topology.sh` | 2.4K | Run tests |
| `quick_start.sh` | 4.4K | Guided setup wizard |
| `validate_setup.sh` | 5.3K | Pre-flight validation |
| `QUICK_START.md` | 6.0K | Quick reference |
| `README_L4S_SETUP.md` | 7.8K | Full setup documentation |
| `CONFIG_REFERENCE.md` | 12K | Network architecture |
| `README_SETUP_GUIDE.md` | 12K | Complete guide |

**Total**: ~57KB of setup files + documentation

---

## ✅ Success Indicators

### After setup_topology.sh:
```bash
$ brctl show
bridge name    bridge id        STP enabled    interfaces
br0            8000.000000000000 no            veth-br0-h
br1            8000.000000000000 no            veth-br1-h
```

### After starting topo1.py:
```bash
Attaching h0 to br0...
Attaching h1 to br0...
Attaching h2 to br1...
L4S ROUTER TOPOLOGY READY
```

### After testing in Mininet:
```bash
mininet> h0 ping h1
PING 192.168.100.11 from 192.168.100.10
32 bytes from 192.168.100.11: icmp_seq=0 ttl=64 time=0.234 ms
```

---

## 🆘 Need Help?

1. **Setup issues?** → Run `./validate_setup.sh`
2. **Connection issues?** → See [README_L4S_SETUP.md](README_L4S_SETUP.md) troubleshooting
3. **Network topology?** → See [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)
4. **Quick answers?** → See [QUICK_START.md](QUICK_START.md)
5. **Everything else?** → See [README_SETUP_GUIDE.md](README_SETUP_GUIDE.md)

---

## 📝 Next Steps

1. ✅ Read this file (you are here!)
2. → Choose your path above
3. → Read recommended documentation
4. → Run recommended scripts
5. → Start your experiments!

---

## 🎓 Learning Resources

- **Mininet**: http://mininet.org/
- **L4S IETF**: https://www.ietf.org/wg/l4s/
- **DualQ Coupled**: https://wiki.ietf.org/en/group/l4s/dualq
- **Linux tc**: https://man7.org/linux/man-pages/man8/tc.8.html

---

## 📞 Still Confused?

```bash
# Easiest path: Guided setup
./quick_start.sh

# It will:
# 1. Check prerequisites
# 2. Verify router connectivity
# 3. Setup topology
# 4. Optionally start Mininet
Finally, if it was not solved yet,
you contact Alireza (ashirmarz@ufscar.br)!
```

**Alternatively**, read the first 3 pages of [README_SETUP_GUIDE.md](README_SETUP_GUIDE.md) then run:

```bash
sudo python3 topo1.py
```

---

## ✨ You're Ready!

Your L4S topology is fully configured. 

**Go to** [README_SETUP_GUIDE.md](README_SETUP_GUIDE.md) or run `./quick_start.sh` to begin!

---

*L4S Router Topology for NiCoLE Project*  
*Setup Date: May 19, 2026*  
*Status: Ready for Testing ✅*

