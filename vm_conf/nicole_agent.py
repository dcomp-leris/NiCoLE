import argparse
import csv
import os
import socket
import struct
import subprocess
import time
from collections import deque

# CONFIG
LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 4000
FORWARD_IP = "192.168.200.10"
FORWARD_PORT = 5004
RTP_CLOCK_RATE = 90000
LINK_CAPACITY_KBPS = 12000
LOG_DIR = "output"
LOG_FILE = "switch_rtp_log.csv"
FLOW_RATE_INTERVAL = 0.01  # 10 ms
QUEUE_POLL_INTERVAL = 0.1
BW_WINDOW_SEC = 2.0
UPGRADE_HOLD_SEC = 3.0
PROFILE_HOLD_SEC = 5.0
UPGRADE_SUSTAIN_SEC = 5.0
SMALL_MARGIN_RATIO = 0.1
BW_FIT_LOW = 0.6
BW_FIT_HIGH = 0.7
QNET_UP = 1.2
QNET_OK = 0.8
QNET_STRESS = 0.6
BACKLOG_ECN_THRESHOLD = 5
ECN_HOLD_SEC = 2.0
HEALTH_INTERVAL_SEC = 5.0
CLASSIC_BACKLOG_LOW_PKTS = 2
CLASSIC_BACKLOG_HIGH_PKTS = 20
FPS_DIFF_UP = 1.0
FPS_DIFF_DOWN = 1.0
FRAME_PKT_HIGH = 60
FRAME_PKT_FIT = 40
STATE_HOLD_SEC = 0.5
BOTTLENECK_IFACE = "enp8s0"

# Args
parser = argparse.ArgumentParser()
parser.add_argument("--marking", action="store_true", help="Enable ECN and DSCP marking")
parser.add_argument("--listen-port", type=int, default=LISTEN_PORT)
parser.add_argument("--forward-ip", default=FORWARD_IP)
parser.add_argument("--forward-port", type=int, default=FORWARD_PORT)
parser.add_argument("--log-dir", default=LOG_DIR)
parser.add_argument("--log-file", default=LOG_FILE)
parser.add_argument("--iface", default=BOTTLENECK_IFACE)
parser.add_argument("--profiles", default="profiles.yaml")
parser.add_argument("--poll-interval", type=float, default=QUEUE_POLL_INTERVAL)
parser.add_argument("--bw-window", type=float, default=BW_WINDOW_SEC)
parser.add_argument("--upgrade-hold-sec", type=float, default=UPGRADE_HOLD_SEC)
parser.add_argument("--profile-hold-sec", type=float, default=PROFILE_HOLD_SEC,
                    help="Minimum seconds between profile changes (lets GCC settle)")
parser.add_argument("--upgrade-sustain-sec", type=float, default=UPGRADE_SUSTAIN_SEC,
                    help="Require sustained bandwidth before upgrading profile/FPS")
parser.add_argument("--small-margin-ratio", type=float, default=SMALL_MARGIN_RATIO)
parser.add_argument("--bw-fit-low", type=float, default=BW_FIT_LOW)
parser.add_argument("--bw-fit-high", type=float, default=BW_FIT_HIGH)
parser.add_argument("--qnet-up", type=float, default=QNET_UP)
parser.add_argument("--qnet-ok", type=float, default=QNET_OK)
parser.add_argument("--qnet-stress", type=float, default=QNET_STRESS)
parser.add_argument("--backlog-low-pkts", type=int, default=CLASSIC_BACKLOG_LOW_PKTS)
parser.add_argument("--backlog-high-pkts", type=int, default=CLASSIC_BACKLOG_HIGH_PKTS)
parser.add_argument("--backlog-ecn-threshold", type=int, default=BACKLOG_ECN_THRESHOLD,
                    help="Avg backlog (pkts) threshold to force ECN=3")
parser.add_argument("--ecn-hold-sec", type=float, default=ECN_HOLD_SEC,
                    help="Seconds to hold ECN=3 once backlog threshold is exceeded")
parser.add_argument("--fps-diff-up", type=float, default=FPS_DIFF_UP)
parser.add_argument("--fps-diff-down", type=float, default=FPS_DIFF_DOWN)
parser.add_argument("--frame-pkt-high", type=int, default=FRAME_PKT_HIGH)
parser.add_argument("--frame-pkt-fit", type=int, default=FRAME_PKT_FIT)
parser.add_argument("--state-hold-sec", type=float, default=STATE_HOLD_SEC)
parser.add_argument("--base-target-fps", type=int, choices=[30, 60, 90, 120], default=None,
                    help="Lock the maximum FPS; if set, upgrades never exceed this value")
args = parser.parse_args()

print(f"📡 Switch running: {args.listen_port} → {args.forward_ip}:{args.forward_port}")
print(f"🧠 Intelligent marking: {args.marking}")

os.makedirs(args.log_dir, exist_ok=True)

try:
    import yaml
    with open(args.profiles, "r") as f:
        profiles = yaml.safe_load(f).get("profiles", [])
except Exception:
    profiles = []

recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
recv_sock.bind((LISTEN_IP, args.listen_port))
forward_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

csv_path = os.path.join(args.log_dir, args.log_file)
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "frame_id", "timestamp", "fps_switch", "fps_server", "rtp_seq", "rtp_ts",
        "frame_pkt_count", "frame_bytes",
        "flow_rate_kbps", "dscp_marked", "ecn_marked",
        "tbf_backlog_pkts", "tbf_backlog_bytes",
        "dualpi2_backlog_pkts", "dualpi2_backlog_bytes",
        "tbf_rate_kbps", "tbf_sent_bytes", "tbf_dropped",
        "dualpi2_dropped", "avail_kbps",
        "target_fps", "target_profile",
        "min_marker_pkt_size", "min_non_marker_pkt_size"
    ])

# State
frame_id = 0
frame_bytes = 0
frame_pkt_count = 0
pkt_sizes = []
last_rtp_ts = None
last_marker_time = None
flow_window = deque()
flow_bytes = 0
flow_start = time.time()
last_queue_poll = 0.0
tbf_backlog_pkts = 0
tbf_backlog_bytes = 0
dualpi2_backlog_pkts = 0
dualpi2_backlog_bytes = 0
tbf_rate_kbps = 0.0
tbf_sent_bytes = 0
tbf_dropped = 0
dualpi2_dropped = 0
avail_kbps = 0.0
state = "normal"
state_until = 0.0
min_marker_pkt_size = None
min_non_marker_pkt_size = None
current_dscp = 36
current_ecn = 0
last_health_time = time.time()
target_fps = None
target_profile = None
current_profile = None
base_target_fps = args.base_target_fps
last_fps_change = 0.0
last_profile_change = 0.0
sent_history = deque()
fps_switch_hist = deque()
avail_hist = deque()
qnet_hist = deque()
backlog_hist = deque()
ecn_force_until = 0.0

def parse_rtp(pkt: bytes):
    if len(pkt) < 12:
        return None
    _, b2, seq, ts, ssrc = struct.unpack("!BBHII", pkt[:12])
    marker = (b2 >> 7) & 1
    return marker, seq, ts, ssrc

def set_dscp_ecn(pkt: bytes, dscp_val: int, ecn_val: int):
    if len(pkt) < 20 or (pkt[0] >> 4) != 4:
        return pkt
    ip = bytearray(pkt[:20])
    ip[1] = ((dscp_val & 0x3F) << 2) | (ecn_val & 0x03)
    # Recalculate IP checksum
    ip[10] = 0
    ip[11] = 0
    s = sum((ip[i] << 8) + ip[i+1] for i in range(0, 20, 2))
    s = (s >> 16) + (s & 0xFFFF)
    s = ~((s >> 16) + s) & 0xFFFF
    ip[10] = s >> 8
    ip[11] = s & 0xFF
    return bytes(ip) + pkt[20:]

def set_socket_tos(sock, dscp_val: int, ecn_val: int):
    tos = ((dscp_val & 0x3F) << 2) | (ecn_val & 0x03)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, tos)

def _parse_backlog(line: str):
    parts = line.split()
    for i, token in enumerate(parts):
        if token == "backlog" and i + 2 < len(parts):
            b = parts[i + 1]
            p = parts[i + 2]
            bytes_val = 0
            pkts_val = 0
            if b.endswith("b"):
                try:
                    bytes_val = int(b[:-1])
                except ValueError:
                    bytes_val = 0
            if p.endswith("p"):
                try:
                    pkts_val = int(p[:-1])
                except ValueError:
                    pkts_val = 0
            return pkts_val, bytes_val
    return None

def _parse_rate_kbps(line: str):
    parts = line.split()
    if "rate" in parts:
        i = parts.index("rate")
        if i + 1 < len(parts):
            token = parts[i + 1]
            if token.endswith("Mbit"):
                try:
                    return float(token[:-4]) * 1000.0
                except ValueError:
                    return 0.0
            if token.endswith("Kbit"):
                try:
                    return float(token[:-4])
                except ValueError:
                    return 0.0
    return 0.0

def _parse_sent_dropped(line: str):
    # Example: Sent 0 bytes 0 pkt (dropped 0, overlimits 0 requeues 0)
    parts = line.replace(",", "").split()
    sent_bytes = None
    dropped = None
    if "Sent" in parts:
        try:
            sent_idx = parts.index("Sent")
            sent_bytes = int(parts[sent_idx + 1])
        except Exception:
            sent_bytes = None
    if "dropped" in parts:
        try:
            drop_idx = parts.index("dropped")
            dropped = int(parts[drop_idx + 1])
        except Exception:
            dropped = None
    return sent_bytes, dropped

def poll_dual_queue():
    try:
        output = subprocess.check_output(
            ["tc", "-s", "qdisc", "show", "dev", args.iface],
            text=True
        )
    except Exception:
        return 0, 0, 0, 0, 0.0, 0, 0, 0

    tbf_pkts = tbf_bytes = 0
    dual_pkts = dual_bytes = 0
    tbf_rate = 0.0
    tbf_sent = 0
    tbf_drop = 0
    dual_drop = 0
    current_qdisc = None

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("qdisc "):
            parts = line.split()
            current_qdisc = parts[1] if len(parts) > 1 else None
            if current_qdisc == "tbf":
                tbf_rate = _parse_rate_kbps(line)
            continue
        if line.startswith("Sent") and current_qdisc:
            sent_bytes, dropped = _parse_sent_dropped(line)
            if current_qdisc == "tbf":
                if sent_bytes is not None:
                    tbf_sent = sent_bytes
                if dropped is not None:
                    tbf_drop = dropped
            elif current_qdisc == "dualpi2":
                if dropped is not None:
                    dual_drop = dropped
            continue
        if "backlog" in line and current_qdisc:
            parsed = _parse_backlog(line)
            if not parsed:
                continue
            pkts_val, bytes_val = parsed
            if current_qdisc == "tbf":
                tbf_pkts, tbf_bytes = pkts_val, bytes_val
            elif current_qdisc == "dualpi2":
                dual_pkts, dual_bytes = pkts_val, bytes_val

    return tbf_pkts, tbf_bytes, dual_pkts, dual_bytes, tbf_rate, tbf_sent, tbf_drop, dual_drop

def _avg_in_window(hist: deque, window_sec: float):
    if not hist:
        return 0.0
    now = time.time()
    while hist and now - hist[0][0] > window_sec:
        hist.popleft()
    if not hist:
        return 0.0
    return sum(v for _, v in hist) / len(hist)

def _min_in_window(hist: deque, window_sec: float):
    if not hist:
        return 0.0
    now = time.time()
    while hist and now - hist[0][0] > window_sec:
        hist.popleft()
    if not hist:
        return 0.0
    return min(v for _, v in hist)

def _profiles_for_fps(fps_target):
    fps_profiles = [p for p in profiles if p.get("fps") == fps_target]
    return sorted(fps_profiles, key=lambda p: p.get("bitrate_kbps", 0))

def _choose_profile_for_fps(fps_target, bw_kbps):
    fps_profiles = [p for p in profiles if p.get("fps") == fps_target]
    if not fps_profiles:
        return None
    # Prefer highest bitrate within 0.7*bitrate <= bw
    fit_profiles = [p for p in fps_profiles if bw_kbps >= args.bw_fit_high * p.get("bitrate_kbps", 0)]
    if fit_profiles:
        return max(fit_profiles, key=lambda p: p.get("bitrate_kbps", 0))
    # If nothing fits, pick closest (but not above too much)
    return min(fps_profiles, key=lambda p: abs(bw_kbps - p.get("bitrate_kbps", 0)))

def _next_lower_profile(fps_profiles, current):
    if current not in fps_profiles:
        return None
    idx = fps_profiles.index(current)
    return fps_profiles[idx - 1] if idx > 0 else current

def _next_higher_profile(fps_profiles, current):
    if current not in fps_profiles:
        return None
    idx = fps_profiles.index(current)
    return fps_profiles[idx + 1] if idx + 1 < len(fps_profiles) else current

def _nearest_fps(targets, value):
    return min(targets, key=lambda t: abs(t - value))

def choose_marking(fps_switch, fps_server, frame_pkt_count, congested):
    fps_diff = fps_server - fps_switch
    # Drop: frame too large or severe congestion
    if frame_pkt_count >= args.frame_pkt_high or congested >= 2:
        return 46, 3, "drop"  # EF + CE
    # Reduce: server faster than switch and queue congested
    if fps_diff > args.fps_diff_down and congested:
        return 48, 3, "reduce"  # CS6 + CE
    # Increase: switch faster and queue clean
    if (fps_switch - fps_server) > args.fps_diff_up and not congested:
        return 34, 1, "up"  # AF41 + ECT(1)
    # Normal
    return 36, 0, "normal"  # AF42 + Not-ECT

while True:
    data, _ = recv_sock.recvfrom(1600)
    now = time.time()
    marker, seq, ts, ssrc = parse_rtp(data) or (None, None, None, None)

    pkt_len = len(data)
    frame_pkt_count += 1
    frame_bytes += pkt_len
    if marker == 1:
        min_marker_pkt_size = pkt_len if min_marker_pkt_size is None else min(min_marker_pkt_size, pkt_len)
    else:
        min_non_marker_pkt_size = pkt_len if min_non_marker_pkt_size is None else min(min_non_marker_pkt_size, pkt_len)

    flow_window.append((now, pkt_len))
    flow_bytes += pkt_len

    while flow_window and now - flow_window[0][0] > FLOW_RATE_INTERVAL:
        old_t, old_size = flow_window.popleft()
        flow_bytes -= old_size

    flow_rate_kbps = (flow_bytes * 8) / 1000 / FLOW_RATE_INTERVAL
    fps_switch = fps_server = 0.0
    dscp_marked = 0
    ecn_marked = 0

    if now - last_queue_poll >= args.poll_interval:
        tbf_backlog_pkts, tbf_backlog_bytes, dualpi2_backlog_pkts, dualpi2_backlog_bytes, tbf_rate_kbps, tbf_sent_bytes, tbf_dropped, dualpi2_dropped = poll_dual_queue()
        last_queue_poll = now

    congested = 1 if tbf_backlog_pkts > args.backlog_low_pkts else 0
    if tbf_backlog_pkts >= args.backlog_high_pkts:
        congested = 2

    if marker == 1:
        # FPS estimation
        if last_marker_time:
            dt = now - last_marker_time
            if dt > 0:
                fps_switch = 1.0 / dt
        last_marker_time = now

        if last_rtp_ts:
            rtp_diff = ts - last_rtp_ts
            if rtp_diff > 0:
                fps_server = RTP_CLOCK_RATE / rtp_diff
        last_rtp_ts = ts

        fps_switch_hist.append((now, fps_switch))
        avg_fps_switch = _avg_in_window(fps_switch_hist, args.bw_window)

        if target_fps is None:
            target_fps = _nearest_fps([30, 60, 90, 120], avg_fps_switch or fps_server or 30)
            if base_target_fps is None:
                base_target_fps = target_fps
        if base_target_fps is not None and target_fps > base_target_fps:
            target_fps = base_target_fps

        # Compute available bandwidth from tc stats (2s window)
        sent_history.append((now, tbf_sent_bytes))
        while sent_history and now - sent_history[0][0] > args.bw_window:
            sent_history.popleft()
        throughput_kbps = 0.0
        if len(sent_history) >= 2:
            t0, b0 = sent_history[0]
            t1, b1 = sent_history[-1]
            dt = max(t1 - t0, 1e-6)
            throughput_kbps = ((b1 - b0) * 8.0) / 1000.0 / dt

        backlog_increasing = False
        if len(sent_history) >= 2:
            backlog_increasing = tbf_backlog_pkts > args.backlog_low_pkts

        if tbf_dropped > 0 or dualpi2_dropped > 0:
            avail_kbps = 0.0
        elif tbf_backlog_pkts == 0 and tbf_dropped == 0 and dualpi2_dropped == 0:
            avail_kbps = max(tbf_rate_kbps - throughput_kbps, 0.0)
        elif backlog_increasing:
            avail_kbps = tbf_rate_kbps * args.small_margin_ratio
        else:
            avail_kbps = max(tbf_rate_kbps - throughput_kbps, 0.0)

        avail_hist.append((now, avail_kbps))
        backlog_hist.append((now, tbf_backlog_pkts))
        avg_backlog = _avg_in_window(backlog_hist, args.bw_window)
        if avg_backlog >= args.backlog_ecn_threshold:
            ecn_force_until = max(ecn_force_until, now + args.ecn_hold_sec)

        # FPS + profile selection logic based on qnet rule
        nearest_fps = _nearest_fps([30, 60, 90, 120], avg_fps_switch or fps_server or target_fps)

        fps_profiles = _profiles_for_fps(target_fps)
        if current_profile is None or current_profile not in fps_profiles:
            current_profile = fps_profiles[-1] if fps_profiles else None
            last_profile_change = now

        r_target = current_profile.get("bitrate_kbps", 0) if current_profile else 0
        qnet = (flow_rate_kbps / r_target) if r_target else 1.0
        qnet_hist.append((now, qnet))

        if qnet < args.qnet_stress:
            # Severe stress: reduce resolution
            if current_profile:
                fps_profiles = _profiles_for_fps(target_fps)
                lower = _next_lower_profile(fps_profiles, current_profile)
                if lower and lower != current_profile and (now - last_profile_change) >= args.profile_hold_sec:
                    current_profile = lower
                    last_profile_change = now
        elif qnet < args.qnet_ok:
            # Compression stress: reduce FPS one step
            if nearest_fps < target_fps:
                target_fps = nearest_fps
                last_fps_change = now
                fps_profiles = _profiles_for_fps(target_fps)
                current_profile = fps_profiles[-1] if fps_profiles else current_profile
                last_profile_change = now
        elif qnet > args.qnet_up:
            # Excess bandwidth: upgrade resolution if sustained
            if current_profile:
                fps_profiles = _profiles_for_fps(target_fps)
                higher = _next_higher_profile(fps_profiles, current_profile)
                sustain_ok = _min_in_window(qnet_hist, args.upgrade_sustain_sec) > args.qnet_up
                if higher and higher != current_profile and sustain_ok and (now - last_profile_change) >= args.profile_hold_sec:
                    current_profile = higher
                    last_profile_change = now

        # Never exceed the initial/base target FPS
        if base_target_fps is not None and target_fps > base_target_fps:
            target_fps = base_target_fps
            fps_profiles = _profiles_for_fps(target_fps)
            if current_profile not in fps_profiles:
                current_profile = fps_profiles[-1] if fps_profiles else current_profile

        target_profile = current_profile

        # Marking logic with state hold
        if args.marking:
            if now < state_until:
                if state == "drop":
                    dscp_marked, ecn_marked = 46, 1
                elif state == "reduce":
                    dscp_marked, ecn_marked = 48, 1
                elif state == "up":
                    dscp_marked, ecn_marked = 34, 1
                else:
                    dscp_marked, ecn_marked = 36, 1
            else:
                if state in {"reduce", "drop"} and (frame_pkt_count > args.frame_pkt_fit or congested):
                    dscp_marked, ecn_marked = (48, 1) if state == "reduce" else (46, 1)
                    state_until = now + args.state_hold_sec
                else:
                    dscp_marked, _, state = choose_marking(
                        fps_switch, fps_server, frame_pkt_count, congested
                    )
                    ecn_marked = 1
                    if state in {"reduce", "drop", "up"}:
                        state_until = now + args.state_hold_sec
                    else:
                        state_until = 0.0

        # Always compute decision DSCP/ECN for logging; apply to packets only with --marking
        if target_profile:
            current_dscp = target_profile.get("dscp", current_dscp)
            current_ecn = 3 if now < ecn_force_until else 1
        else:
            current_dscp = dscp_marked
            current_ecn = 3 if now < ecn_force_until else ecn_marked

        # CSV log
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                frame_id, round(time.time(), 3), round(fps_switch, 2), round(fps_server, 2), seq, ts,
                frame_pkt_count, frame_bytes,
                round(flow_rate_kbps, 2), current_dscp, current_ecn,
                tbf_backlog_pkts, tbf_backlog_bytes,
                dualpi2_backlog_pkts, dualpi2_backlog_bytes,
                round(tbf_rate_kbps, 2), tbf_sent_bytes, tbf_dropped,
                dualpi2_dropped, round(avail_kbps, 2),
                target_fps, target_profile.get("name") if target_profile else "",
                min_marker_pkt_size, min_non_marker_pkt_size
            ])

        print(f"🎬 Frame {frame_id} | Rflow={flow_rate_kbps:.1f} Kbps | DSCP={current_dscp} | ECN={current_ecn} | FPS={fps_switch:.2f}")
        frame_id += 1
        frame_bytes = 0
        frame_pkt_count = 0
        min_marker_pkt_size = None
        min_non_marker_pkt_size = None

        if time.time() - last_health_time >= HEALTH_INTERVAL_SEC:
            print(
                f"🩺 Switch health | state={state} | tbf={tbf_backlog_pkts}p "
                f"dualpi2={dualpi2_backlog_pkts}p | avail={avail_kbps:.1f} kbps | "
                f"dscp={current_dscp} ecn={current_ecn}"
            )
            last_health_time = time.time()

    if args.marking:
        set_socket_tos(forward_sock, current_dscp, current_ecn)

    forward_sock.sendto(data, (args.forward_ip, args.forward_port))
