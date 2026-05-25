#!/usr/bin/env python3
# Author: Alireza Shirmarz
# Location: Leris, UFSCar
# Date: 2026-05-20
"""
NICoLE VM agent for router-based RTP/WebRTC flow telemetry and DSCP/ECN control.

This script runs on the router VM and watches flows across the bottleneck interface.
It extracts the requested features in 400 ms windows, sends them to a local GGUF model,
and applies ECN/DSCP actions when conditions persist.

Requirements on the router VM:
  sudo apt install python3-pip python3-netfilterqueue
  pip3 install scapy llama-cpp-python
  sudo iptables -I FORWARD -i enp7s0 -o enp8s0 -j NFQUEUE --queue-num 1
  sudo iptables -I FORWARD -i enp8s0 -o enp7s0 -j NFQUEUE --queue-num 1

Run:
  sudo python3 ~/nicole_agent/nicole_agent.py \
      --iface enp8s0 \
      --model ~/nicole_agent/nicole-q4.gguf \
      --marking
"""

import argparse
import binascii
import csv
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections import deque, defaultdict

try:
    from netfilterqueue import NetfilterQueue
    from scapy.all import IP, UDP, TCP, Raw
except ImportError as exc:
    print("Missing required Python modules:", exc)
    print("Install: sudo apt install python3-netfilterqueue && pip3 install scapy")
    sys.exit(1)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

RTP_CLOCK_RATE = 90000
WINDOW_SEC = 0.4
QUEUE_POLL_SEC = 0.1
PROFILE_DSCP = {0: 32, 1: 34, 2: 40, 3: 46}

parser = argparse.ArgumentParser(description="NICoLE VM flow agent")
parser.add_argument("--iface", default="enp8s0", help="Bottleneck interface on router VM")
parser.add_argument("--model", default="~/nicole_agent/nicole-q4.gguf",
                    help="Path to GGUF model")
parser.add_argument("--queue-num", type=int, default=1, help="NFQUEUE queue number")
parser.add_argument("--marking", action="store_true", help="Enable ECN/DSCP marking")
parser.add_argument("--log-dir", default="~/nicole_agent/logs")
parser.add_argument("--log-file", default="nicole_agent_flow_log.csv")
args = parser.parse_args()

if Llama is None:
    print("Missing llama_cpp. Install with: pip3 install llama-cpp-python")
    sys.exit(1)

os.makedirs(args.log_dir, exist_ok=True)
log_path = os.path.join(args.log_dir, args.log_file)

model = Llama(model_path=args.model)

lock = threading.Lock()
flow_states = {}
queue_samples = deque()
last_rollup = time.time()
running = True
nfqueue = None

class FlowState:
    def __init__(self, flow_key):
        self.flow_key = flow_key
        self.flow_id = crc16("|".join(map(str, flow_key)).encode())
        self.packet_sizes = deque()
        self.ecn_bits = deque()
        self.frame_sizes = deque()
        self.ifgs = deque()
        self.ifgr = deque()
        self.last_marker_time = None
        self.last_marker_ts = None
        self.current_frame_bytes = 0
        self.last_decision = None
        self.repeat_count = 0
        self.active_action = None
        self.latest_model_output = None

    def prune(self, cutoff):
        while self.packet_sizes and self.packet_sizes[0][0] < cutoff:
            self.packet_sizes.popleft()
        while self.ecn_bits and self.ecn_bits[0][0] < cutoff:
            self.ecn_bits.popleft()
        while self.frame_sizes and self.frame_sizes[0][0] < cutoff:
            self.frame_sizes.popleft()
        while self.ifgs and self.ifgs[0][0] < cutoff:
            self.ifgs.popleft()
        while self.ifgr and self.ifgr[0][0] < cutoff:
            self.ifgr.popleft()

    def add_packet(self, ts, pkt_len, ecn_flag, rtp_marker=None, rtp_ts=None):
        self.packet_sizes.append((ts, pkt_len))
        self.ecn_bits.append((ts, 1 if ecn_flag else 0))
        self.current_frame_bytes += pkt_len
        if rtp_marker is None:
            return
        if rtp_marker == 1:
            self.frame_sizes.append((ts, self.current_frame_bytes))
            self.current_frame_bytes = 0
            if self.last_marker_time is not None:
                self.ifgs.append((ts - self.last_marker_time, ts))
            self.last_marker_time = ts
            if self.last_marker_ts is not None and rtp_ts is not None:
                diff = (rtp_ts - self.last_marker_ts) / RTP_CLOCK_RATE
                if diff > 0:
                    self.ifgr.append((diff, ts))
            self.last_marker_ts = rtp_ts

    def snapshot(self, cutoff):
        self.prune(cutoff)
        packet_count = len(self.packet_sizes)
        ps_avg = (sum(v for _, v in self.packet_sizes) / packet_count) if packet_count else 0.0
        fs_avg = (sum(v for _, v in self.frame_sizes) / len(self.frame_sizes)) if self.frame_sizes else 0.0
        ifgs_avg = (sum(v for v, _ in self.ifgs) / len(self.ifgs)) if self.ifgs else 0.0
        ifgr_avg = (sum(v for v, _ in self.ifgr) / len(self.ifgr)) if self.ifgr else 0.0
        e_avg = (sum(v for _, v in self.ecn_bits) / len(self.ecn_bits)) if self.ecn_bits else 0.0
        return {
            "flow_id": self.flow_id,
            "packets": packet_count,
            "ps_avg": ps_avg,
            "fs_avg": fs_avg,
            "ifgs_avg": ifgs_avg,
            "ifgr_avg": ifgr_avg,
            "ecn_avg": e_avg,
        }

    def update_decision(self, decision):
        if decision == self.last_decision:
            self.repeat_count += 1
        else:
            self.last_decision = decision
            self.repeat_count = 1
        if self.repeat_count >= 2 and decision is not None:
            n, ecn_pred = decision
            self.active_action = (PROFILE_DSCP.get(n, 36), 1)
        else:
            self.active_action = None

    def __repr__(self):
        return f"FlowState({self.flow_key}, id={self.flow_id}, action={self.active_action})"


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0) & 0xFFFF


def parse_rtp(payload: bytes):
    if len(payload) < 12:
        return None
    b1, b2 = payload[0], payload[1]
    version = b1 >> 6
    if version != 2:
        return None
    marker = (b2 >> 7) & 1
    seq = int.from_bytes(payload[2:4], "big")
    ts = int.from_bytes(payload[4:8], "big")
    return marker, seq, ts


def parse_queue_backlog(output: str):
    classic_pkts = 0
    l4s_pkts = 0
    current = None
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("qdisc "):
            current = line.split()[1]
            continue
        if "backlog" not in line:
            continue
        m = re.search(r"backlog\s+\S+\s+(\d+)p", line)
        if not m:
            continue
        pkts = int(m.group(1))
        if "classic" in line.lower() or (current and "classic" in current.lower()):
            classic_pkts = pkts
        elif "l4s" in line.lower() or (current and "l4s" in current.lower()):
            l4s_pkts = pkts
        elif current == "dualpi2":
            classic_pkts = pkts
    return classic_pkts, l4s_pkts


def poll_queue():
    while running:
        try:
            output = subprocess.check_output(
                ["tc", "-s", "qdisc", "show", "dev", args.iface], text=True, stderr=subprocess.DEVNULL
            )
            cq, lq = parse_queue_backlog(output)
        except Exception:
            cq, lq = 0, 0
        ts = time.time()
        with lock:
            queue_samples.append((ts, cq, lq))
            while queue_samples and ts - queue_samples[0][0] > WINDOW_SEC:
                queue_samples.popleft()
        time.sleep(QUEUE_POLL_SEC)


def queue_averages(cutoff):
    with lock:
        valid = [x for x in queue_samples if x[0] >= cutoff]
    if not valid:
        return 0.0, 0.0
    return (sum(x[1] for x in valid) / len(valid), sum(x[2] for x in valid) / len(valid))


def prompt_model(ps, fs, ifgs, ifgr, cq, lq, e_avg):
    prompt = (
        "You are a network controller. "
        "Return only JSON with keys E, C, N. "
        "E is ECN decision (0 or 1). "
        "C is current profile (0-3). "
        "N is next profile (0-3).\n"
        f"Features: PS={ps:.2f}, FS={fs:.2f}, IFGS={ifgs:.4f}, IFGR={ifgr:.4f}, CQ={cq:.2f}, LQ={lq:.2f}, E={e_avg:.2f}\n"
        "Example: {\"E\": 1, \"C\": 1, \"N\": 2}"
    )
    response = model.create(prompt=prompt, max_tokens=64, temperature=0.0)
    text = response.choices[0].text.strip() if hasattr(response, 'choices') else str(response)
    return parse_model_response(text)


def parse_model_response(text: str):
    text = text.replace("\n", " ")
    e_match = re.search(r'"?E"?\s*[:=]\s*([01])', text)
    c_match = re.search(r'"?C"?\s*[:=]\s*([0-3])', text)
    n_match = re.search(r'"?N"?\s*[:=]\s*([0-3])', text)
    if not (e_match and c_match and n_match):
        return None
    return int(e_match.group(1)), int(c_match.group(1)), int(n_match.group(1))


def format_avg(value):
    return f"**{value:.3f}**"


def log_flow_report(flow_id, snapshot, cq, lq, action, model_output):
    with open(log_path, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(), flow_id,
            snapshot["ps_avg"], snapshot["fs_avg"], snapshot["ifgs_avg"], snapshot["ifgr_avg"],
            cq, lq, snapshot["ecn_avg"],
            action[0] if action else "", action[1] if action else "",
            model_output or ""
        ])
    print(
        f"FLOW {flow_id} | PS={format_avg(snapshot['ps_avg'])} "
        f"FS={format_avg(snapshot['fs_avg'])} IFGS={format_avg(snapshot['ifgs_avg'])} "
        f"IFGR={format_avg(snapshot['ifgr_avg'])} CQ={format_avg(cq)} "
        f"LQ={format_avg(lq)} E={format_avg(snapshot['ecn_avg'])} "
        f"MODEL={model_output} ACTION={action}"
    )


def rollup(now):
    cutoff = now - WINDOW_SEC
    avg_cq, avg_lq = queue_averages(cutoff)
    snapshots = []
    with lock:
        for state in flow_states.values():
            snapshot = state.snapshot(cutoff)
            snapshots.append((state, snapshot))
    for state, snapshot in snapshots:
        if snapshot["packets"] == 0:
            continue
        model_decision = prompt_model(
            snapshot["ps_avg"], snapshot["fs_avg"], snapshot["ifgs_avg"], snapshot["ifgr_avg"],
            avg_cq, avg_lq, snapshot["ecn_avg"]
        )
        if model_decision is None:
            action = None
        else:
            _, current_profile, next_profile = model_decision
            action = None
            if current_profile != next_profile:
                action = (PROFILE_DSCP[next_profile], 1)
            state.update_decision((next_profile, model_decision[0]))
        log_flow_report(state.flow_id, snapshot, avg_cq, avg_lq, state.active_action, model_decision)


def packet_handler(pkt):
    global last_rollup
    raw = pkt.get_payload()
    scapy_pkt = IP(raw)
    if scapy_pkt.version != 4:
        pkt.accept()
        return
    proto = scapy_pkt.proto
    sport = dport = 0
    payload = b""
    rtp_marker = None
    rtp_ts = None
    if proto == 17 and UDP in scapy_pkt:
        sport = scapy_pkt[UDP].sport
        dport = scapy_pkt[UDP].dport
        payload = bytes(scapy_pkt[UDP].payload)
    elif proto == 6 and TCP in scapy_pkt:
        sport = scapy_pkt[TCP].sport
        dport = scapy_pkt[TCP].dport
        payload = bytes(scapy_pkt[TCP].payload)
    flow_key = (scapy_pkt.src, scapy_pkt.dst, sport, dport, proto)
    with lock:
        state = flow_states.get(flow_key)
        if state is None:
            state = FlowState(flow_key)
            flow_states[flow_key] = state
    ecn_flag = bool(scapy_pkt.tos & 0x03)
    rtp_data = parse_rtp(payload)
    if rtp_data is not None:
        rtp_marker, _, rtp_ts = rtp_data
    state.add_packet(time.time(), len(raw), ecn_flag, rtp_marker, rtp_ts)
    if state.active_action and args.marking:
        dscp_val, ecn_val = state.active_action
        scapy_pkt.tos = ((dscp_val & 0x3F) << 2) | (ecn_val & 0x03)
        del scapy_pkt.chksum
        raw = bytes(scapy_pkt)
        pkt.set_payload(raw)
    pkt.accept()
    now = time.time()
    if now - last_rollup >= WINDOW_SEC:
        last_rollup = now
        threading.Thread(target=rollup, args=(now,), daemon=True).start()


def cleanup(signum, frame):
    global running
    print("Stopping nicole_agent...")
    running = False
    if nfqueue:
        nfqueue.unbind()
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

with open(log_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "flow_id", "ps_avg", "fs_avg", "ifgs_avg", "ifgr_avg",
        "cq_avg", "lq_avg", "ecn_avg", "action_dscp", "action_ecn", "model_output"
    ])

poll_thread = threading.Thread(target=poll_queue, daemon=True)
poll_thread.start()

nfqueue = NetfilterQueue()
nfqueue.bind(args.queue_num, packet_handler)
print(f"NICoLE agent listening on NFQUEUE {args.queue_num} and interface {args.iface}")
try:
    nfqueue.run()
except KeyboardInterrupt:
    cleanup(None, None)
