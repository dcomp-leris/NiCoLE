# NICoLE: Are In-Network LLM-Based Agents Cost-Feasible for RTP Video Streaming?

[![NICoLE](https://img.shields.io/badge/NICoLE-Presentation-blue)](https://docs.google.com/presentation/d/1LHkMz7mNkxGzYqVPaLeMySLA2KP4OjW1hrWsEONwt4c/edit?usp=sharing)
[![NICoLE](https://img.shields.io/badge/NICoLE-Paper-yellow)](https://github.com/dcomp-leris/NiCoLE/blob/main/2026151137.pdf)
[![NICoLE](https://img.shields.io/badge/NICoLE-Huggingface-green)](https://huggingface.co/alirezashirmarz/NICoLE-LLM)


*This paper was accepted and presented in the IFIP Networking 2026 Conference.*
*This repository is run to present the NICoLE!*

NICoLE (Network Inference for Congestion-aware Low-latency Optimization) is a compact LLM-based controller for congestion-aware RTP/WebRTC adaptive video streaming.

<img width="905" height="448" alt="image" src="https://github.com/user-attachments/assets/ca4fed0d-30e6-4007-b111-758d7931fa8a" />



# Requirements

## 1 - WebRTC + GCC 
- Go to Gst_WebRTC
- Run sender/receiver and signalling

        cd ./Gst_WebRTC
  
## 2 - L4S/DualQ Support device

        cd ./vm_conf

## 3 - Mininet Simple Topology
        
        cd ./Topo

## 4 - NICoLE Agent Model

- Go to the huggingface and find the following fine-tuned model!


HF Model:

          alirezashirmarz/NICoLE-LLM 
          
GGUF Model:

        alirezashirmarz/NICoLE-LLM-GGUF

Download and add models (HF & GGUF) to this project:

        cd ./models
        git clone https://huggingface.co/alirezashirmarz/NICoLE-LLM
        

**NICoLE predicts**:

* ECN
* Current Profile (CP)
* Next Profile (NP)

from RTP packetization and queue telemetry using compact symbolic prompting.

**The project demonstrates**:

* real-time WebRTC streaming
* congestion-aware profile adaptation
* compact LLM inference
* GGUF quantized deployment
* edge AI feasibility for networking

---

# Features

* RTP/WebRTC adaptive streaming
* Compact symbolic prompting
* Hugging Face inference
* GGUF / llama.cpp deployment
* CPU deployment benchmarking
* Congestion-aware profile switching
* QoE-aware adaptation
* Reproducible topology and dataset generation

---

# Repository Structure

```text
NICoLE/
├── Gst_WebRTC/
├── models/
├── gguf/
├── topology/
├── webrtc/
├── inference/
├── scripts/
├── results/
└── README.md
```

---

# Topology

```text
Sender ---- Router/Bottleneck ---- Receiver
                 |
          Background Traffic
```

* Bottleneck bandwidth: 40 Mbps
* Background traffic: up to 38 Mbps
* Streaming: RTP/WebRTC
* Adaptive profiles: P0/P1/P2/P3

---

# Profiles

| Profile | Resolution | FPS                |
| ------- | ---------- | ------------------ |
| P0      | 3840×2160  | 30 / 60 / 90 / 120 |
| P1      | 1920×1080  | 30 / 60 / 90 / 120 |
| P2      | 1280×720   | 30 / 60 / 90 / 120 |
| P3      | 640×360    | 30 / 60 / 90 / 120 |

GoP duration:

* 2 seconds

---

# Prompt Format

Input order:

```text
PS FS IFGS IFGR CQ LQ E
```

Output order:

```text
E C N
```

Example:

```text
I:PS FS IFGS IFGR CQ LQ E
O:E C N

U:1400,40,34,33,2,0,0

A:
```

Expected output:

```text
0,1,1
```

---

# Quick Start

## Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/NICoLE.git
cd NICoLE
```

---

# Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Hugging Face Inference

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "YOUR_USERNAME/NICoLE-LLM"

tok = AutoTokenizer.from_pretrained(model_id)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="auto"
)

prompt = """I:PS FS IFGS IFGR CQ LQ E
O:E C N

U:1400,40,34,33,2,0,0

A:"""

inputs = tok(prompt, return_tensors="pt").to(model.device)

out = model.generate(
    **inputs,
    max_new_tokens=6,
    do_sample=False
)

print(tok.decode(out[0], skip_special_tokens=True))
```

---

# GGUF / llama.cpp

```bash
./llama-cli \
-no-cnv \
-t 4 \
-m nicole-q4.gguf \
-p "I:PS FS IFGS IFGR CQ LQ E
O:E C N

U:1400,40,34,33,2,0,0

A:" \
-n 6 \
--temp 0 \
--top-k 1
```

---

# CPU Benchmark

| Threads | Response (ms) | Decisions/sec |
| ------- | ------------- | ------------- |
| 1       | 1325          | 0.75          |
| 2       | 624           | 1.60          |
| 4       | 343           | 2.91          |
| 8       | 904           | 1.11          |

Best deployment:

* 4 threads
* 343 ms response time
* 2.91 decisions/sec

---

# Dataset

The dataset was generated using:

* RTP/WebRTC streaming
* dynamic bandwidth reduction
* congestion-induced adaptation
* QoE-aware profile switching

QoE metrics:

* VMAF
* receiver FPS
* stall ratio

---

# Citation

```bibtex
@misc{nicole,
  title={NICoLE: Congestion-Aware LLM Controller for RTP/WebRTC Streaming},
  author={Alireza Shirmarz},
  year={2026}
}
```



# NiCoLE Router VM and Host Experiment README


## Router VM setup

1) Install required packages

On the router VM:

```bash
sudo apt update
sudo apt install -y python3-pip python3-netfilterqueue iptables iproute2
sudo pip3 install scapy llama-cpp-python
```

2) Enable IP forwarding

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

3) Enforce total 40 Mbps on `enp8s0`

This makes the router’s `enp8s0` path the 40 Mbps bottleneck:

```bash
sudo tc qdisc replace dev enp8s0 root handle 1: htb default 11
sudo tc class replace dev enp8s0 parent 1: classid 1:1 htb rate 40mbit ceil 40mbit
sudo tc qdisc replace dev enp8s0 parent 1:1 handle 10: dualpi2
```

4) Capture router traffic in NFQUEUE

```bash
sudo iptables -I FORWARD -i enp7s0 -o enp8s0 -j NFQUEUE --queue-num 1
sudo iptables -I FORWARD -i enp8s0 -o enp7s0 -j NFQUEUE --queue-num 1
```

5) Run the NICoLE agent

```bash
sudo python3 /home/alireza/Myprojects/NiCoLE/vm_conf/nicole_agent.py \
    --iface enp8s0 \
    --model /home/alireza/Myprojects/NiCoLE/models/nicole-q4.gguf \
    --marking
```

The agent logs results to:

`/home/alireza/Myprojects/NiCoLE/vm_conf/logs/nicole_agent_flow_log.csv`

It samples every `0.4s`, extracts `PS`, `FS`, `IFGS`, `IFGR`, `CQ`, `LQ`, `E`, runs the GGUF model, and applies DSCP/ECN marking.

---

## Host setup and scenario run

1) Prepare the Mininet topology

On the host machine:

```bash
cd /home/alireza/Myprojects/NiCoLE/Topo
sudo ./setup_topology.sh
```

2) Start the topology

```bash
sudo python3 /home/alireza/Myprojects/NiCoLE/Topo/topo1.py
```

3) Confirm host roles

In Mininet CLI:

```text
h0 → 192.168.100.10 (iperf3 generator)
h1 → 192.168.100.11 (WebRTC video source)
h2 → 192.168.200.10 (client / receiver)
```

---

## Traffic scenario for experiment

### A) Start iperf3 traffic from `h0` to `h2`

In Mininet CLI:

```bash
h2 iperf3 -s &
h0 iperf3 -c 192.168.200.10 -u -b 35M -t 60 &
```

This makes `h0` the sender and `h2` the receiving client.

### B) Start WebRTC video from `h1` to `h2`

Use your existing `Gst_WebRTC` modules:

- Run the signaling server first
- Run `sender.py` on the source side
- Run `receiver.py` on the client side

Note: the current `Gst_WebRTC` scripts use `ws://127.0.0.1:8765`. For Mininet hosts, either run the signaling server in the same namespace or change it to bind an IP reachable by `h1` and `h2`.

Example:

```bash
# On a machine reachable by h1/h2
cd /home/alireza/Myprojects/NiCoLE/Gst_WebRTC
python3 server.py
```

Then on `h1`:

```bash
h1 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/sender.py &
```

And on `h2`:

```bash
h2 python3 /home/alireza/Myprojects/NiCoLE/Gst_WebRTC/receiver.py &
```

---

## Collecting the experiment

### Check the agent log

On the router VM:

```bash
tail -f /home/alireza/Myprojects/NiCoLE/vm_conf/logs/nicole_agent_flow_log.csv
```

### Verify bottleneck shaping

On the router VM:

```bash
sudo tc -s qdisc show dev enp8s0
```

### Stop the agent cleanly

Press `Ctrl-C` in the NICoLE agent terminal.

### Clear NFQUEUE rules when done

```bash
sudo iptables -D FORWARD -i enp7s0 -o enp8s0 -j NFQUEUE --queue-num 1
sudo iptables -D FORWARD -i enp8s0 -o enp7s0 -j NFQUEUE --queue-num 1
```

---

## Summary

- `h0` = iperf3 traffic generator
- `h1` = WebRTC video source
- `h2` = watched client
- Router bottleneck `enp8s0` = 40 Mbps
- Agent file = `/home/alireza/Myprojects/NiCoLE/vm_conf/nicole_agent.py`
- Log output = `/home/alireza/Myprojects/NiCoLE/vm_conf/logs/nicole_agent_flow_log.csv`
