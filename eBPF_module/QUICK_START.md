# eBPF Adaptive Streaming - Quick Start

## 1. Copy my plan

```
Receiver (h2)
├─ eBPF monitor (receiver_ebpf_listener.py)
│  ├─ Captures RTP packets + DSCP/ECN marks
│  ├─ Aggregates ECN signals every 1 second
│  └─ Sends profile feedback UDP → h1:10000
│
└─ WebRTC Receiver (receiver.py)
   └─ Displays video stream

Sender (h1)
├─ Signaling Server (server.py)
│  └─ Relays SDP/ICE for WebRTC
│
└─ Adaptive Sender (adaptive_sender.py)
   ├─ Listens on UDP port 10000 for profile feedback
   ├─ Dynamically rebuilds GStreamer pipeline
   └─ Adjusts bitrate/FPS based on selected profile

Network
├─ h0 ↔ Router: iperf3 background traffic (35 Mbps)
│  └─ Creates congestion → triggers ECN marks
│
├─ h1 → Router: RTP stream with ECN marks
│  └─ 40 Mbps bottleneck with DualPI2
│
└─ h2 ← Router: RTP stream received + DSCP/ECN extracted
   └─ eBPF detects congestion → sends feedback
```

## 2. No router VM modifications needed

The existing `nc_agent.py` on the router VM is independent. This adaptive streaming system runs **inside Mininet** on the hosts h1 and h2, and the router simply marks packets with ECN/DSCP via the 40 Mbps bottleneck.

## 3. Files created

| File | Purpose |
|------|---------|
| `eBPF_module/receiver_ebpf_listener.py` | eBPF listener on h2 |
| `Gst_WebRTC/adaptive_sender.py` | Adaptive encoder on h1 |
| `eBPF_module/README_ADAPTIVE_STREAMING.md` | Full documentation |

## 4. Key features

✅ **Receiver-driven adaptation**: h2 analyzes network quality and sends profile feedback
✅ **Profile switching**: sender dynamically switches between 4 profiles (high/medium/low/very_low)
✅ **eBPF-based monitoring**: real-time DSCP/ECN extraction from RTP packets
✅ **Non-blocking changes**: pipeline rebuilt while maintaining WebRTC connection
✅ **Configurable thresholds**: ECN ratios determine profile selection

## 5. Quick test flow

```bash
# Terminal 1: Start topology
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo python3 topo1.py

# Mininet CLI - Terminal 2 onwards:

# Start signaling server
h1 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/server.py &

# Start adaptive sender
h1 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/adaptive_sender.py &

# Start eBPF listener (setup clsact first if needed)
h2 sudo tc qdisc add dev eth0 root clsact 2>/dev/null
h2 sudo python3 /home/alireza/Myprojects/NiCoLE/eBPF_module/receiver_ebpf_listener.py &

# Start receiver
h2 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/receiver.py &

# (Optional) Add competing traffic to trigger adaptation
h0 iperf3 -s &
h0 iperf3 -c 192.168.200.10 -u -b 35M -t 60 &

# Watch adaptation happen (in another window)
# The eBPF listener will show profile changes as ECN signals arrive
```

## 6. Expected behavior

1. **No congestion (0-10% ECN)**: Profile 0 selected → 4000 kbps, 30 FPS
2. **Light congestion (10-30% ECN)**: Profile 1 selected → 3000 kbps, 24 FPS
3. **Moderate congestion (30-50% ECN)**: Profile 2 selected → 2000 kbps, 18 FPS
4. **Heavy congestion (>50% ECN)**: Profile 3 selected → 1000 kbps, 12 FPS

When you add iperf3 traffic (35 Mbps on 40 Mbps bottleneck), the receiver will see ECN marks increase, triggering profile downgrades.

## 7. Integration with router VM agent

The router's `nicole_agent.py` independently:
- Monitors flows via NFQUEUE
- Extracts RTP features (PS, FS, IFGS, IFGR)
- Queries the GGUF model
- Sets DSCP/ECN marks

The eBPF listener on h2 **reads** those marks and provides **per-receiver feedback**. They complement each other:
- **Router (`nicole_agent.py`)**: network-wide flow management
- **Receiver eBPF + Adaptive sender**: per-stream adaptation

## 8. Logs

Check eBPF listener window for:
```
[WINDOW] packets=1200, ECN counts={0: 1100, 3: 100}, selected_profile=1
→ Sent profile 1 (medium) to 192.168.100.11:10000
```

Check adaptive sender window for:
```
[Feedback] received profile 1 (medium) from...
[Sender] rebuilding pipeline for profile 1...
→ Profile changed: 0 → 1 (medium)
```
