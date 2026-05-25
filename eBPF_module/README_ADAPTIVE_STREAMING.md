# eBPF-based Adaptive WebRTC Streaming README

## Overview

This system provides **dynamic bitrate adaptation for WebRTC streaming** based on real-time network quality signals captured via eBPF on the receiver side.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ h1 (Sender): Adaptive WebRTC Encoder                        │
│  - adaptive_sender.py: receives profile feedback             │
│  - Dynamically adjusts bitrate, FPS, encoder preset          │
│  - Sends H.264 RTP stream to h2                             │
└─────────────────────────────────────────────────────────────┘
                            │
                    RTP Stream + DSCP/ECN marks
                            │
  ┌─────────────────────────▼──────────────────────────────────┐
  │ Router enp8s0 (40 Mbps bottleneck)                          │
  │  - Marks packets with DSCP/ECN based on congestion         │
  │  - DualPI2 qdisc enforces shaping                          │
  └─────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ h2 (Receiver): eBPF-based Feedback Generator                │
  │  - receiver_ebpf_listener.py: monitors DSCP/ECN marks       │
  │  - Aggregates signals every 1 second                        │
  │  - Decides profile (0-3) based on congestion               │
  │  - Sends UDP feedback to h1 on port 10000                 │
  └─────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. Receiver eBPF Listener (`eBPF_module/receiver_ebpf_listener.py`)

Runs on **h2** (receiver).

**What it does:**
- Attaches to NIC ingress to capture incoming RTP packets
- Extracts DSCP and ECN marks from IP TOS field
- Aggregates ECN signals over 1-second windows
- Maps ECN congestion levels to profiles (0-3)
- Sends profile selection back to sender via UDP port 10000

**Profile selection logic:**
```
ECN Ratio = (packets with ECN=3) / total_packets

if ECN_ratio > 50%: profile = 3 (very_low)   →  1000 kbps, 12 FPS
else if ECN_ratio > 30%: profile = 2 (low)   →  2000 kbps, 18 FPS
else if ECN_ratio > 10%: profile = 1 (medium) → 3000 kbps, 24 FPS
else: profile = 0 (high)                      →  4000 kbps, 30 FPS
```

**Key files:**
- `receiver_ebpf_listener.py`: eBPF listener with adaptive profile logic

---

### 2. Adaptive WebRTC Sender (`Gst_WebRTC/adaptive_sender.py`)

Runs on **h1** (sender).

**What it does:**
- Listens for profile feedback on UDP port 10000
- When profile changes, updates encoder configuration
- Rebuilds GStreamer pipeline with new settings
- Maintains WebRTC connection while adapting

**Supported profiles:**
```
Profile 0: bitrate=4000 kbps, FPS=30, preset=fast    [High Quality]
Profile 1: bitrate=3000 kbps, FPS=24, preset=fast    [Medium Quality]
Profile 2: bitrate=2000 kbps, FPS=18, preset=ultrafast [Low Quality]
Profile 3: bitrate=1000 kbps, FPS=12, preset=ultrafast [Very Low Quality]
```

**Key features:**
- Non-blocking profile changes (pipeline rebuild over ~500ms)
- WebSocket signaling to receiver
- Automatic QP (quantization parameter) adjustment

---

### 3. Signaling Server (`Gst_WebRTC/server.py`)

Runs on **h1** (same machine as adaptive_sender).

**What it does:**
- Relays WebRTC SDP offers/answers and ICE candidates
- Binds on `0.0.0.0:8765` for Mininet host access

---

### 4. WebRTC Receiver (`Gst_WebRTC/receiver.py`)

Runs on **h2**.

**What it does:**
- Receives RTP stream from sender
- Decodes and displays video
- Monitors stream quality (FPS, bitrate, packet loss)

---

## Setup and Installation

### Prerequisites

**On host machine:**
```bash
sudo apt update
sudo apt install -y mininet python3-pip python3-gi gstreamer1.0-tools \
  gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-libav
```

**On h1 and h2 (inside Mininet):**
- `websockets` (for signaling)
- `bcc` (for eBPF on receiver)
- GStreamer bindings

### Installation steps

```bash
# 1. Install base packages
sudo apt install -y python3-pip python3-netfilterqueue iptables iproute2

# 2. Setup host venv
cd /home/alireza/Myprojects/NiCoLE
python3 -m venv venv_host
source venv_host/bin/activate
pip install websockets

# 3. Setup router VM (if separate)
python3 -m venv venv_vm
source venv_vm/bin/activate
pip install scapy llama-cpp-python NetfilterQueue
```

---

## Running the Experiment

### Step 1: Start the Mininet topology

```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo ./setup_topology.sh              # prepare bridges
sudo python3 topo1.py                 # start topology
```

You should see Mininet CLI prompt.

---

### Step 2: Start signaling server on h1

```bash
h1 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/server.py &
```

Expected output:
```
Server started ws://0.0.0.0:8765
```

---

### Step 3: Start adaptive sender on h1

```bash
h1 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/adaptive_sender.py &
```

Expected output:
```
============================================================
Adaptive WebRTC Sender
============================================================
Feedback port: 10000
Signal server: ws://192.168.100.11:8765
Initial profile: 1 (medium)

Profile definitions:
  0: high (4000 kbps, 30 FPS)
  1: medium (3000 kbps, 24 FPS)
  2: low (2000 kbps, 18 FPS)
  3: very_low (1000 kbps, 12 FPS)
============================================================
```

---

### Step 4: Start eBPF receiver listener on h2

```bash
h2 sudo python3 /home/alireza/Myprojects/NiCoLE/eBPF_module/receiver_ebpf_listener.py \
    --interface eth0 \
    --sender-ip 192.168.100.11 \
    --sender-port 10000 \
    --window 1.0 &
```

Expected output:
```
[Receiver eBPF listener started]
  Interface: eth0
  Sender: 192.168.100.11:10000
  Aggregation window: 1.0s

Profile definitions:
  0: high (4000 kbps, 30 FPS)
  1: medium (3000 kbps, 24 FPS)
  2: low (2000 kbps, 18 FPS)
  3: very_low (1000 kbps, 12 FPS)

Listening for RTP packets...
```

> **Note:** eBPF requires `clsact` qdisc. If listener fails, run:
> ```bash
> h2 sudo tc qdisc add dev eth0 root clsact
> ```

---

### Step 5: Start WebRTC receiver on h2

```bash
h2 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/receiver.py &
```

Expected output:
```
NEW PAD: recv_rtcp_src_0
Receiving video...
[STATS] FPS=24.5 Bitrate=2950 kbps
```

---

### Step 6: Start background traffic (optional)

To simulate network congestion and trigger adaptive bitrate changes:

```bash
h0 iperf3 -s &
h0 iperf3 -c 192.168.200.10 -u -b 35M -t 120 &
```

This adds 35 Mbps UDP traffic, leaving only 5 Mbps free on the 40 Mbps bottleneck.

---

## Observing Adaptation

### On h2 (receiver), watch eBPF feedback:

```bash
# (already running in background, tail the monitor)
h2 tail -f /tmp/receiver_monitor.log
```

You should see output like:
```
[WINDOW] packets=1245, ECN counts={0: 1200, 3: 45}, selected_profile=1
→ Sent profile 1 (medium) to 192.168.100.11:10000
```

### On h1 (sender), watch encoder adaptation:

```bash
# Check sender log (if redirected)
h1 tail -f /tmp/sender.log
```

You should see:
```
[Feedback] received profile 2 (low) from ('192.168.100.11', <port>)
[Sender] rebuilding pipeline for profile 2...
→ Profile changed: 1 → 2 (low)
[Pipeline] rebuilding with profile 2...
```

### On h2 (receiver), watch video quality:

```bash
h2 tail -f /tmp/receiver_stats.log
```

You should see bitrate changes:
```
[STATS] FPS=30.0  Bitrate=3950 kbps    (high profile)
[STATS] FPS=24.1  Bitrate=2980 kbps    (medium profile after congestion)
[STATS] FPS=18.2  Bitrate=1995 kbps    (low profile during heavy load)
```

---

## Configuration

### Receiver eBPF listener

Arguments:
```bash
--interface ETH0           # NIC to monitor (default: eth0)
--sender-ip 192.168.100.11 # Sender address (default: h1)
--sender-port 10000        # Feedback UDP port (default: 10000)
--window 1.0               # Aggregation window in seconds (default: 1.0)
```

### Adaptive sender

Edit `adaptive_sender.py`:
```python
FEEDBACK_PORT = 10000          # Must match receiver's --sender-port
SIGNAL_SERVER = "ws://192.168.100.11:8765"
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480
VIDEO_SOURCE = "test"  # test / webcam / files

# Modify PROFILES dict to change bitrate/FPS targets
PROFILES = {
    0: {"name": "high", "bitrate": 5000, "fps": 30, ...},
    ...
}
```

---

## Troubleshooting

### eBPF attachment fails
```
✗ Failed to attach eBPF: ...
```

Fix:
```bash
h2 sudo tc qdisc add dev eth0 root clsact
```

Then restart receiver_ebpf_listener.py.

### Sender doesn't receive feedback
Check UDP connectivity:
```bash
h1 nc -ul 10000 &  # listen on port 10000
h2 echo "test" | nc -u 192.168.100.11 10000
```

### WebRTC connection fails
Verify signaling server is running:
```bash
h1 netstat -tlnup | grep 8765
```

Should show `0.0.0.0:8765` listening.

---

## Key Metrics

### From receiver eBPF listener:
- **ECN marks percentage**: indicates network congestion
- **Selected profile**: 0-3 based on congestion level
- **Packet count per window**: traffic volume

### From adaptive sender:
- **Current profile**: active encoding settings
- **Bitrate**: RTP bitrate in kbps
- **FPS**: frames per second

### From webrtc receiver:
- **Received bitrate**: measured RTP bitrate
- **FPS**: actual playback frame rate
- **Frame size**: encoded frame bytes

---

## Files Summary

| File | Location | Purpose |
|------|----------|---------|
| `receiver_ebpf_listener.py` | `eBPF_module/` | eBPF-based RTP quality monitor on receiver |
| `adaptive_sender.py` | `Gst_WebRTC/` | WebRTC sender with adaptive bitrate |
| `server.py` | `Gst_WebRTC/` | WebRTC signaling server |
| `receiver.py` | `Gst_WebRTC/` | WebRTC receiver with stats |

---

## Protocol: Profile Feedback Message

**Format:** UDP message from receiver to sender
```
PROFILE:<profile_id>,<profile_name>
```

**Example:**
```
PROFILE:2,low
```

**Fields:**
- `<profile_id>`: 0-3 integer
- `<profile_name>`: descriptive name (high/medium/low/very_low)

---

## Future Enhancements

1. **Receiver-side codec switching**: adapt H.264 vs VP8 based on profile
2. **Router integration**: feedback from router's `nicole_agent.py` to sender
3. **Multi-bitrate playlist**: SFU-style quality switching
4. **RTCP feedback**: use RTCP-XR for explicit feedback channel
