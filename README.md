# NICoLE: Are In-Network LLM-Based Agents Cost-Feasible for RTP Video Streaming?

[![NICoLE](https://img.shields.io/badge/NICoLE-Presentation-blue)](https://docs.google.com/presentation/d/1LHkMz7mNkxGzYqVPaLeMySLA2KP4OjW1hrWsEONwt4c/edit?usp=sharing)
[![NICoLE](https://img.shields.io/badge/NICoLE-Paper-yellow)](https://github.com/dcomp-leris/NiCoLE/blob/main/2026151137.pdf)
[![NICoLE](https://img.shields.io/badge/Model-Huggingface-green)](https://huggingface.co/alirezashirmarz/NICoLE-LLM)
[![NICoLE](https://img.shields.io/badge/Conference-IFIPNetworking2026-red)](https://networking.ifip.org/2026/index.php/program/detailed-program)
[![NICoLE](https://img.shields.io/badge/L4S-RFC9332)](https://github.com/L4STeam/linux.git)



*This paper was accepted and will be presented in the IFIP Networking 2026 Conference on 2026/05/24.*

**Note**: NICoLE (Network Inference for Congestion-aware Low-latency Optimization) is a compact LLM-based controller for congestion-aware RTP/WebRTC adaptive video streaming.

# Prerequirements Installation
**Host Computer**
```text
sudo apt update &&
sudo apt install -y python3-gi python3-websockets gstreamer1.0-tools \
gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
gstreamer1.0-plugins-bad gstreamer1.0-libav
```

**L4S Enabled Router**
```text
sudo apt update &&
sudo apt install -y python3-pip python3-netfilterqueue iptables iproute2 &&
sudo pip3 install scapy llama-cpp-python
```
# NICoLE Active Componets
**1 - WebRTC + GCC** 
- Go to Gst_WebRTC
- Run sender/receiver and signalling

        cd ./Gst_WebRTC
  
**2 - L4S/DualQ Enabled Network Device**

        cd ./vm_conf

**3 - Mininet Simple Topology**
        
        cd ./Topo

**4 - NICoLE Agent Model**

- Go to the huggingface and find the following fine-tuned model!


Huggingface (HF Model):

          alirezashirmarz/NICoLE-LLM 
          
Huggingface (GGUF Model):

        alirezashirmarz/NICoLE-LLM-GGUF

Download and add models (HF & GGUF) to this project:

        cd ./models
        git clone https://huggingface.co/alirezashirmarz/NICoLE-LLM

---

# Repository Structure

```text
NICoLE/
├── 2026151137.pdf
├── Gst_WebRTC
│   ├── README.md
│   ├── receiver.py
│   ├── sender.py
│   └── server.py
├── models
│   ├── NICoLE-LLM
│   │   ├── config.json
│   │   ├── generation_config.json
│   │   ├── model.safetensors
│   │   ├── nicole-f16.gguf
│   │   ├── nicole-q4.gguf
│   │   ├── README.md
│   │   ├── special_tokens_map.json
│   │   ├── tokenizer_config.json
│   │   ├── tokenizer.json
│   │   └── tokenizer.model
│   ├── nicole-q4.gguf
│   └── README.md
├── README.md
├── requirements-host.txt
├── requirements-vm.txt
├── Topo
│   ├── CONFIG_REFERENCE.md
│   ├── QUICK_START.md
│   ├── quick_start.sh
│   ├── README_L4S_SETUP.md
│   ├── README.md
│   ├── README_SETUP_GUIDE.md
│   ├── README_SHORT.md
│   ├── setup_router.sh
│   ├── setup_topology.sh
│   ├── test_topology.sh
│   ├── topo1.py
│   └── validate_setup.sh
└── vm_conf
    ├── nicole_agent.py
    └── __pycache__
        └── nicole_agent.cpython-312.pyc
```

# NICoLE End-to-End Setup 

## NiCoLE Router VM and Host Experiment README


### Router VM setup

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
sudo python3 ./NiCoLE/vm_conf/nicole_agent.py \
    --iface enp8s0 \
    --model ./NiCoLE/models/nicole-q4.gguf \
    --marking
```

The agent logs results to:

`./NiCoLE/vm_conf/logs/nicole_agent_flow_log.csv`

It samples every `0.4s`, extracts `PS`, `FS`, `IFGS`, `IFGR`, `CQ`, `LQ`, `E`, runs the GGUF model, and applies DSCP/ECN marking.

---

### Host setup and scenario run

1) Prepare the Mininet topology

On the host machine:

```bash
cd ./NiCoLE/Topo
sudo ./setup_topology.sh
```

2) Start the topology

```bash
sudo python3 ./NiCoLE/Topo/topo1.py
```

3) Confirm host roles

In Mininet CLI:

```text
h0 → 192.168.100.10 (iperf3 generator)
h1 → 192.168.100.11 (WebRTC video source)
h2 → 192.168.200.10 (client / receiver)
```

---

### Traffic scenario for experiment

#### A) Start iperf3 traffic from `h0` to `h2`

In Mininet CLI:

```bash
h2 iperf3 -s &
h0 iperf3 -c 192.168.200.10 -u -b 35M -t 60 &
```

This makes `h0` the sender and `h2` the receiving client.

#### B) Start WebRTC video from `h1` to `h2`

Use your existing `Gst_WebRTC` modules:

- Run the signaling server first
- Run `sender.py` on the source side
- Run `receiver.py` on the client side

Note: the current `Gst_WebRTC` scripts use `ws://127.0.0.1:8765`. For Mininet hosts, either run the signaling server in the same namespace or change it to bind an IP reachable by `h1` and `h2`.

Example:

```bash
# On a machine reachable by h1/h2
cd ./NiCoLE/Gst_WebRTC
python3 server.py
```

Then on `h1`:

```bash
h1 python3 ./NiCoLE/Gst_WebRTC/sender.py &
```

And on `h2`:

```bash
h2 python3 ./NiCoLE/Gst_WebRTC/receiver.py &
```

---

### Collecting the experiment

#### Check the agent log

On the router VM:

```bash
tail -f ./NiCoLE/nicole_agent/nicole_agent_flow_log.csv
```

#### Verify bottleneck shaping

On the router VM:

```bash
sudo tc -s qdisc show dev enp8s0
```

#### Stop the agent cleanly

Press `Ctrl-C` in the NICoLE agent terminal.

#### Clear NFQUEUE rules when done

```bash
sudo iptables -D FORWARD -i enp7s0 -o enp8s0 -j NFQUEUE --queue-num 1
sudo iptables -D FORWARD -i enp8s0 -o enp7s0 -j NFQUEUE --queue-num 1
```

---

### Summary

- `h0` = iperf3 traffic generator
- `h1` = WebRTC video source
- `h2` = watched client
- Router bottleneck `enp8s0` = 40 Mbps
- Agent file = `./NiCoLE/vm_conf/nicole_agent.py`
- Log output = `./NiCoLE/vm_conf/logs/nicole_agent_flow_log.csv`

### Cite
```text
- Alireza Shirmarz, Fabio Luciano Verdi, Gyanesh Patra, Gergely Pongracz,"NICoLE: Are In-Network LLM-Based Agents
Cost-Feasible for RTP Video Streaming?", IEEE/IFIP Networking, Switzerland 2026.

```

