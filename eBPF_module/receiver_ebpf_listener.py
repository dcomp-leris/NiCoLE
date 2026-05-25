#!/usr/bin/env python3
"""
Receiver-side eBPF listener for RTP/WebRTC flow quality monitoring.

This script runs on h2 (receiver) and:
1. Monitors incoming RTP packets for DSCP/ECN marks via eBPF
2. Aggregates ECN signals over 1 second windows
3. Decides on a profile (0-3) based on congestion signals
4. Sends profile selection back to the sender (h1) via UDP

Profile mapping:
  0: high bitrate   (4000 kbps, FPS 30, preset fast)
  1: medium bitrate (3000 kbps, FPS 24, preset fast)
  2: lower bitrate  (2000 kbps, FPS 18, preset ultrafast)
  3: low bitrate    (1000 kbps, FPS 12, preset ultrafast)
"""

from bcc import BPF
from socket import socket, AF_INET, SOCK_DGRAM
import struct
import time
import argparse

# Configuration
SENDER_IP = "192.168.100.11"  # h1 address
SENDER_PORT = 10000           # profile feedback port
INTERFACE = "eth0"             # receiver RTP interface
AGGREGATION_WINDOW = 1.0       # seconds

# Profile definitions
PROFILES = {
    0: {"name": "high",    "bitrate": 4000, "fps": 30, "preset": "fast"},
    1: {"name": "medium",  "bitrate": 3000, "fps": 24, "preset": "fast"},
    2: {"name": "low",     "bitrate": 2000, "fps": 18, "preset": "ultrafast"},
    3: {"name": "very_low","bitrate": 1000, "fps": 12, "preset": "ultrafast"},
}

# eBPF program to monitor incoming RTP packets
BPF_TEXT = """
#include <uapi/linux/ptrace.h>
#include <linux/ip.h>
#include <linux/udp.h>
#include <linux/if_ether.h>

struct rtp_info {
    u8 dscp;
    u8 ecn;
    u16 rtp_port;
};

BPF_PERF_OUTPUT(events);

int monitor_rtp(struct __sk_buff *skb)
{
    struct rtp_info pkt = {};
    
    // Load IP version
    u8 ip_version = 0;
    bpf_skb_load_bytes(skb, ETH_HLEN, &ip_version, 1);
    if ((ip_version >> 4) != 4)
        return TC_ACT_OK;
    
    // Load TOS field (DSCP + ECN)
    u8 tos = 0;
    bpf_skb_load_bytes(skb, ETH_HLEN + 1, &tos, 1);
    pkt.dscp = tos >> 2;
    pkt.ecn = tos & 0x03;
    
    // Load UDP destination port
    u16 udp_dport = 0;
    bpf_skb_load_bytes(skb, ETH_HLEN + 22, &udp_dport, 2);
    pkt.rtp_port = bpf_ntohs(udp_dport);
    
    events.perf_submit_skb(skb, skb->len, &pkt, sizeof(pkt));
    
    return TC_ACT_OK;
}
"""

parser = argparse.ArgumentParser(description="Receiver eBPF listener for RTP quality feedback")
parser.add_argument("--interface", default=INTERFACE, help="Interface to monitor (default: eth0)")
parser.add_argument("--sender-ip", default=SENDER_IP, help="Sender IP address (h1)")
parser.add_argument("--sender-port", type=int, default=SENDER_PORT, help="Sender feedback port")
parser.add_argument("--window", type=float, default=AGGREGATION_WINDOW, help="Aggregation window (seconds)")
args = parser.parse_args()

# Initialize eBPF
b = BPF(text=BPF_TEXT)
fn = b.load_func("monitor_rtp", BPF.SCHED_CLS)

try:
    b.attach_tc(dev=args.interface, fn_name="monitor_rtp", attach_point="ingress")
    print(f"✓ eBPF attached to {args.interface} ingress")
except Exception as e:
    print(f"✗ Failed to attach eBPF: {e}")
    print("  Try: sudo tc qdisc add dev eth0 root clsact")
    exit(1)

# UDP socket for sending feedback
sock = socket(AF_INET, SOCK_DGRAM)

# State tracking
ecn_counts = {}  # {ecn_value: count}
last_aggregation = time.time()
current_profile = 0
last_profile = None

def decide_profile():
    """Decide profile based on ECN signals."""
    global ecn_counts, current_profile
    
    total = sum(ecn_counts.values())
    if total == 0:
        return 0  # No ECN, use high profile
    
    ce_count = ecn_counts.get(3, 0)  # ECN=3 is Congestion Experienced
    ecn_ratio = ce_count / total if total > 0 else 0
    
    if ecn_ratio > 0.5:
        return 3  # High congestion: very low profile
    elif ecn_ratio > 0.3:
        return 2  # Moderate congestion: low profile
    elif ecn_ratio > 0.1:
        return 1  # Some congestion: medium profile
    else:
        return 0  # Minimal congestion: high profile

def send_profile_feedback(profile):
    """Send profile selection to sender."""
    global last_profile
    
    if profile == last_profile:
        return
    
    last_profile = profile
    profile_name = PROFILES[profile]["name"]
    
    msg = f"PROFILE:{profile},{profile_name}"
    try:
        sock.sendto(msg.encode(), (args.sender_ip, args.sender_port))
        print(f"→ Sent profile {profile} ({profile_name}) to {args.sender_ip}:{args.sender_port}")
    except Exception as e:
        print(f"✗ Failed to send feedback: {e}")

def process_event(cpu, data, size):
    """Process eBPF packet events."""
    global ecn_counts, last_aggregation, current_profile
    
    event = b["events"].event(data)
    ecn = event.ecn
    
    # Aggregate ECN counts
    ecn_counts[ecn] = ecn_counts.get(ecn, 0) + 1
    
    # Check if aggregation window expired
    now = time.time()
    if now - last_aggregation >= args.window:
        # Decide on profile
        current_profile = decide_profile()
        
        # Send feedback
        send_profile_feedback(current_profile)
        
        # Log statistics
        total = sum(ecn_counts.values())
        print(f"[WINDOW] packets={total}, ECN counts={ecn_counts}, selected_profile={current_profile}")
        
        # Reset counters
        ecn_counts = {}
        last_aggregation = now

print(f"Receiver eBPF listener started")
print(f"  Interface: {args.interface}")
print(f"  Sender: {args.sender_ip}:{args.sender_port}")
print(f"  Aggregation window: {args.window}s")
print(f"\nProfile definitions:")
for p, cfg in PROFILES.items():
    print(f"  {p}: {cfg['name']} ({cfg['bitrate']} kbps, {cfg['fps']} FPS, {cfg['preset']} preset)")
print("\nListening for RTP packets...")

b["events"].open_perf_buffer(process_event)

try:
    while True:
        b.perf_buffer_poll()
except KeyboardInterrupt:
    print("\nShutting down...")
    b.remove_tc(dev=args.interface, attach_point="ingress")
    sock.close()
