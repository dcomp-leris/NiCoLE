# NICoLE: Are In-Network LLM-Based Agents Cost-Feasible for RTP Video Streaming?

[![CG](https://img.shields.io/badge/NICoLE-Presentation-blue)](https://docs.google.com/presentation/d/1LHkMz7mNkxGzYqVPaLeMySLA2KP4OjW1hrWsEONwt4c/edit?usp=sharing)

*This paper was accepted and presented in the IFIP Networking 2026 Conference.*
*This repository is run to present the NICoLE!*

NICoLE (Network Inference for Congestion-aware Low-latency Optimization) is a compact LLM-based controller for congestion-aware RTP/WebRTC adaptive video streaming.

<img width="905" height="448" alt="image" src="https://github.com/user-attachments/assets/ca4fed0d-30e6-4007-b111-758d7931fa8a" />


NICoLE predicts:

* ECN
* Current Profile (CP)
* Next Profile (NP)

from RTP packetization and queue telemetry using compact symbolic prompting.

The project demonstrates:

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
├── dataset/
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

