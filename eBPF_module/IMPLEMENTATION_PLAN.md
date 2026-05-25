# eBPF Adaptive Streaming - Implementation Summary

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    MININET TOPOLOGY (h0, h1, h2)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐        ┌──────────────────┐                 │
│  │   h0 (iperf3)    │        │  h1 (Sender)     │                 │
│  │  192.168.100.10  │        │ 192.168.100.11   │                 │
│  ├──────────────────┤        ├──────────────────┤                 │
│  │ UDP Traffic Gen  │        │ server.py        │                 │
│  │ 35 Mbps to h2    │        │ (Signaling)      │                 │
│  └────────┬─────────┘        ├──────────────────┤                 │
│           │                  │ adaptive_sender..py │              │
│           │                  │ (WebRTC Encoder) │                 │
│           │                  │ - Listens UDP 10000        │       │
│           │                  │ - Profiles 0-3            │       │
│           │                  │ - Rebuilds pipeline       │       │
│           │                  └────────┬─────────┘                 │
│           │                           │                           │
│           │     20 Mbps iperf3        │   RTP Stream              │
│           │     ◄──────────────────────┤   (H.264, adaptive BR)   │
│           │                           │                           │
│           └──────────────┬────────────┘                           │
│                          │                                         │
├──────────────────────────┼─────────────────────────────────────────┤
│                          │          ROUTER VM                      │
│                   DualPI2 on enp8s0                               │
│                   40 Mbps Bottleneck                             │
│                   ├─ Marks packets with DSCP/ECN               │
│                   │  (nicole_agent.py or system marking)       │
│                   ▼                                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────┐                                  │
│  │      h2 (Receiver)       │                                  │
│  │   192.168.200.10         │                                  │
│  ├──────────────────────────┤                                  │
│  │ receiver.py              │  (decodes + displays video)      │
│  ├──────────────────────────┤                                  │
│  │ receiver_ebpf_listener.py│  ◄─── RTP with DSCP/ECN marks  │
│  │ ├─ eBPF on eth0 ingress  │                                  │
│  │ ├─ Captures DSCP/ECN     │                                  │
│  │ ├─ Aggregates 1s windows │                                  │
│  │ ├─ Decides profile 0-3   │                                  │
│  │ └─ Sends UDP to h1:10000 │                                  │
│  │     (PROFILE:N,name)     │                                  │
│  └──────────────────────────┘                                  │
│        │                                                        │
│        └─────────────────────────────────────────┐             │
│          UDP Feedback (profile change signal)    │             │
│                                                   │             │
└───────────────────────────────────────────────────┼─────────────┘
                                                    │
                                          Back to h1:10000
```

---

## Component Breakdown

### 1. Receiver eBPF Listener (`receiver_ebpf_listener.py`)

**Location:** h2 (receiver)

**Functionality:**
- eBPF program attaches to eth0 ingress
- Extracts IP TOS byte (DSCP + ECN bits)
- Tracks packet-level ECN marks in 1-second windows
- Computes ECN congestion ratio
- Maps congestion level → profile (0, 1, 2, or 3)

**Output:** UDP message `PROFILE:<id>,<name>` sent to h1 port 10000

**Dependencies:**
- `bcc` library (eBPF compiler collection)
- Root privilege (for tc qdisc + eBPF)

**Thresholds:**
```python
if ecn_ratio > 0.5:    # >50% marked as CE
    profile = 3  # very_low: 1000 kbps, 12 FPS
elif ecn_ratio > 0.3:  # 30-50% marked
    profile = 2  # low: 2000 kbps, 18 FPS
elif ecn_ratio > 0.1:  # 10-30% marked
    profile = 1  # medium: 3000 kbps, 24 FPS
else:                  # <10% marked
    profile = 0  # high: 4000 kbps, 30 FPS
```

---

### 2. Adaptive WebRTC Sender (`adaptive_sender.py`)

**Location:** h1 (sender)

**Functionality:**
- Listens on UDP port 10000 for profile feedback
- `AdaptiveEncoder` class manages encoder configuration
- When profile changes, rebuilds GStreamer pipeline
- Maintains WebRTC connection via websocket
- Non-blocking pipeline rebuild (~500ms latency)

**Features:**
- **FeedbackListener** thread: background UDP listener
- **AdaptiveEncoder**: builds encoder/source strings for each profile
- **Pipeline rebuild**: stops old pipeline, creates new one, resumes

**Profile structure:**
```python
{
    0: {"name": "high",    "bitrate": 4000, "fps": 30, "preset": "fast"},
    1: {"name": "medium",  "bitrate": 3000, "fps": 24, "preset": "fast"},
    2: {"name": "low",     "bitrate": 2000, "fps": 18, "preset": "ultrafast"},
    3: {"name": "very_low","bitrate": 1000, "fps": 12, "preset": "ultrafast"},
}
```

**GStreamer pipeline:**
- Video source: `videotestsrc` (test pattern) or webcam/files
- Encoder: `x264enc` with configurable bitrate, preset, GOP, QP
- RTP payload: `rtph264pay`
- Output: WebRTC `webrtcbin`

---

### 3. Signaling Server (`server.py`)

**No changes needed.** Already present, just ensure it binds to `0.0.0.0:8765`.

---

### 4. WebRTC Receiver (`receiver.py`)

**No changes needed.** Displays video and logs quality metrics.

---

## Data Flow

### Normal Operation

1. **h1 sends RTP**: adaptive_sender.py streams H.264 via WebRTC
2. **Router marks packets**: DualPI2 adds ECN marks to RTP packets
3. **h2 receives RTP**: packets arrive with DSCP/ECN marks
4. **eBPF reads marks**: receiver_ebpf_listener.py captures TOS byte
5. **Aggregation**: counts ECN marks every 1 second
6. **Profile decision**: maps ECN ratio to profile number (0-3)
7. **Feedback sent**: UDP message `PROFILE:N,name` → h1:10000
8. **Sender adapts**: receives feedback, rebuilds pipeline with new bitrate/FPS
9. **Quality changes**: next RTP packets use new encoding settings

### Example timeline

```
T=0s:  h1: profile=1 (3000 kbps, 24 FPS)
       → Sends RTP at 3000 kbps

T=5s:  Network load increases (h0 iperf3 traffic)
       → Router applies ECN marks to RTP packets
       → h2 receives 40 packets/sec, 35 have ECN=3

T=6s:  h2 eBPF window closes
       → ECN ratio = 35/40 = 87.5% > 50%
       → Decides profile=3 (very_low)
       → Sends `PROFILE:3,very_low` to h1:10000

T=6.1s: h1 receives feedback
        → adaptive_sender logs: "profile 1 → 3"
        → Rebuilds pipeline

T=6.5s: h1 sends RTP at new profile (1000 kbps, 12 FPS)
        → Network congestion eases
        → Receivers see bitrate drop but video still flowing

T=10s: Load decreases
       → h2 eBPF sees only 5% ECN marks
       → Decides profile=0 (high)
       → Sends feedback to h1
       → h1 ramps up to 4000 kbps, 30 FPS
```

---

## Configuration & Customization

### Adaptive sender bitrate targets

Edit `adaptive_sender.py` `PROFILES` dict:
```python
PROFILES = {
    0: {"name": "high",    "bitrate": 5000, "fps": 30, "preset": "fast"},
    1: {"name": "medium",  "bitrate": 3000, "fps": 24, "preset": "fast"},
    2: {"name": "low",     "bitrate": 2000, "fps": 18, "preset": "ultrafast"},
    3: {"name": "very_low","bitrate": 1000, "fps": 12, "preset": "ultrafast"},
}
```

### eBPF listener thresholds

Edit `receiver_ebpf_listener.py` `decide_profile()` function:
```python
if ecn_ratio > 0.5:    # Adjust thresholds here
    return 3
elif ecn_ratio > 0.3:
    return 2
```

### Aggregation window

Command-line:
```bash
h2 python3 receiver_ebpf_listener.py --window 2.0  # 2 seconds
```

---

## Integration with router VM

The router's `nicole_agent.py` runs independently and:
1. Monitors all flows via NFQUEUE
2. Extracts RTP features (PS, FS, IFGS, IFGR)
3. Queries GGUF model
4. **Sets DSCP/ECN marks on packets**

The eBPF listener on h2:
1. **Reads** those DSCP/ECN marks
2. Provides **per-receiver feedback**
3. Triggers sender adaptation

**No changes needed to router** — it already marks packets. The eBPF listener simply uses those marks as input.

---

## Test Scenarios

### Scenario 1: No congestion
```bash
# Run sender + receiver + eBPF listener
# No iperf3 traffic
# Expected: Profile 0 (high), 4000 kbps, 30 FPS
```

### Scenario 2: Light congestion
```bash
# Run iperf3 at 10 Mbps
# Expected: Profile 0-1, gradual bitrate reduction
```

### Scenario 3: Heavy congestion
```bash
# Run iperf3 at 35 Mbps (only 5 Mbps free)
# Expected: Profile 3, 1000 kbps, 12 FPS
# Receiver video still plays but lower quality
```

### Scenario 4: Congestion + recovery
```bash
# Start iperf3 at 35 Mbps → observe downgrades
# Stop iperf3 → observe upgrades back to high profile
# Total time: ~10-15 seconds for full cycle
```

---

## Files Checklist

| File | Created | Purpose |
|------|---------|---------|
| `eBPF_module/receiver_ebpf_listener.py` | ✅ | eBPF packet monitor on h2 |
| `Gst_WebRTC/adaptive_sender.py` | ✅ | Adaptive encoder on h1 |
| `eBPF_module/README_ADAPTIVE_STREAMING.md` | ✅ | Full documentation |
| `eBPF_module/QUICK_START.md` | ✅ | Quick-start guide |
| `Gst_WebRTC/server.py` | ⚠️ | Ensure `0.0.0.0:8765` binding |
| `Gst_WebRTC/receiver.py` | ⚠️ | No changes, works as-is |

---

## Summary

✅ **Receiver-driven feedback**: eBPF listener on h2 monitors incoming RTP quality  
✅ **Adaptive encoding**: sender dynamically adjusts profiles 0-3  
✅ **Non-blocking changes**: pipeline rebuild while maintaining connection  
✅ **ECN-based decisions**: congestion detection via IP TOS marks  
✅ **Router agnostic**: works with any ECN/DSCP marking system  
✅ **Configurable profiles**: easy to customize bitrate/FPS targets  

No router VM changes needed — existing `nicole_agent.py` marks packets, eBPF reads marks.
