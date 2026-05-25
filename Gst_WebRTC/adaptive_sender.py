#!/usr/bin/env python3
"""
Adaptive WebRTC Sender with eBPF-based feedback control.

This runs on h1 (sender) and:
1. Receives profile feedback from h2 (receiver eBPF listener) via UDP
2. Dynamically adapts encoder parameters
3. Reconstructs GStreamer pipeline with new settings
4. Sends WebRTC stream to receiver

Profile mapping (received from receiver):
  0: high bitrate   (4000 kbps, FPS 30, preset fast)
  1: medium bitrate (3000 kbps, FPS 24, preset fast)
  2: lower bitrate  (2000 kbps, FPS 18, preset ultrafast)
  3: low bitrate    (1000 kbps, FPS 12, preset ultrafast)
"""

import asyncio
import websockets
import gi
import json
import threading
import socket
from collections import deque

gi.require_version('Gst', '1.0')
gi.require_version('GstWebRTC', '1.0')
from gi.repository import Gst, GstWebRTC, GstSdp

Gst.init(None)

# Configuration
FEEDBACK_PORT = 10000
SIGNAL_SERVER = "ws://192.168.100.11:8765"
VIDEO_SOURCE = "test"  # test / webcam / files
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 480

# Profile definitions
PROFILES = {
    0: {"name": "high",    "bitrate": 4000, "fps": 30, "preset": "fast"},
    1: {"name": "medium",  "bitrate": 3000, "fps": 24, "preset": "fast"},
    2: {"name": "low",     "bitrate": 2000, "fps": 18, "preset": "ultrafast"},
    3: {"name": "very_low","bitrate": 1000, "fps": 12, "preset": "ultrafast"},
}

class AdaptiveEncoder:
    """Encoder configuration handler."""
    
    def __init__(self, profile=1):
        self.current_profile = profile
        self.config = PROFILES[profile].copy()
        self.config["width"] = VIDEO_WIDTH
        self.config["height"] = VIDEO_HEIGHT
        self.config["codec"] = "h264"
        self.config["qp_min"] = 70
        self.config["qp_max"] = 80
        self.config["tune"] = "zerolatency"
        self.config["bframes"] = 0
    
    def set_profile(self, profile):
        """Switch to a different profile."""
        if profile not in PROFILES or profile == self.current_profile:
            return False
        
        old = self.current_profile
        self.current_profile = profile
        self.config.update(PROFILES[profile])
        print(f"  → Profile changed: {old} → {profile} ({PROFILES[profile]['name']})")
        return True
    
    def build_encoder_string(self):
        """Build GStreamer encoder pipeline string."""
        c = self.config
        enc = (
            f"x264enc "
            f"bitrate={c['bitrate']} "
            f"key-int-max={c.get('gop', 30)} "
            f"qp-min={c.get('qp_min', 70)} "
            f"qp-max={c.get('qp_max', 80)} "
            f"speed-preset={c.get('preset', 'fast')} "
            f"tune={c.get('tune', 'zerolatency')} "
            f"bframes={c.get('bframes', 0)} ! "
            f"rtph264pay config-interval=1"
        )
        return enc
    
    def build_video_source_string(self):
        """Build GStreamer video source pipeline string."""
        c = self.config
        if VIDEO_SOURCE == "test":
            src = f"videotestsrc is-live=true ! video/x-raw,width={c['width']},height={c['height']},framerate={c['fps']}/1"
        elif VIDEO_SOURCE == "webcam":
            src = f"v4l2src ! videoconvert ! videoscale ! video/x-raw,width={c['width']},height={c['height']},framerate={c['fps']}/1"
        else:
            src = f"videotestsrc is-live=true ! video/x-raw,width={c['width']},height={c['height']},framerate={c['fps']}/1"
        return src
    
    def build_pipeline_string(self):
        """Build complete pipeline string."""
        src = self.build_video_source_string()
        enc = self.build_encoder_string()
        caps = "application/x-rtp,media=video,encoding-name=H264,payload=96"
        
        pipeline = f"""
        webrtcbin name=send bundle-policy=max-bundle
        {src} ! {enc} ! {caps} ! send.
        """.replace("\n", " ")
        
        return pipeline


class FeedbackListener(threading.Thread):
    """Listens for profile feedback from receiver."""
    
    def __init__(self, adapter):
        super().__init__(daemon=True)
        self.adapter = adapter
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", FEEDBACK_PORT))
    
    def run(self):
        print(f"[Feedback] listening on port {FEEDBACK_PORT}...")
        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                msg = data.decode().strip()
                
                if msg.startswith("PROFILE:"):
                    parts = msg.split(":")[1].split(",")
                    profile = int(parts[0])
                    name = parts[1] if len(parts) > 1 else ""
                    
                    print(f"[Feedback] received profile {profile} ({name}) from {addr}")
                    self.adapter.on_profile_feedback(profile)
                    
            except Exception as e:
                print(f"[Feedback] error: {e}")


class AdaptiveSender:
    """WebRTC sender with adaptive encoding."""
    
    def __init__(self):
        self.encoder = AdaptiveEncoder(profile=1)
        self.pipe = None
        self.webrtc = None
        self.ws = None
        self.loop = None
        self.rebuild_needed = False
        self.feedback_listener = FeedbackListener(self)
        self.feedback_listener.start()
    
    def on_profile_feedback(self, profile):
        """Handle profile feedback from receiver."""
        if self.encoder.set_profile(profile):
            print(f"[Sender] rebuilding pipeline for profile {profile}...")
            self.rebuild_needed = True
    
    def build_pipeline(self):
        """Build the GStreamer pipeline."""
        pipeline_str = self.encoder.build_pipeline_string()
        print(f"[Pipeline] {pipeline_str}")
        
        self.pipe = Gst.parse_launch(pipeline_str)
        self.webrtc = self.pipe.get_by_name("send")
        
        print(f"[Pipeline] created with profile {self.encoder.current_profile} "
              f"({self.encoder.config['name']})")
    
    async def run(self):
        self.loop = asyncio.get_running_loop()
        self.build_pipeline()
        
        print(f"[WebRTC] connecting to {SIGNAL_SERVER}...")
        self.ws = await websockets.connect(SIGNAL_SERVER)
        
        self.webrtc.connect("on-negotiation-needed", self.on_negotiation)
        self.webrtc.connect("on-ice-candidate", self.on_ice)
        
        self.pipe.set_state(Gst.State.PLAYING)
        
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                if "answer" in data:
                    self.set_remote(data["answer"])
                elif "ice" in data:
                    self.webrtc.emit("add-ice-candidate", 0, data["ice"])
                
                # Check if pipeline rebuild is needed
                if self.rebuild_needed:
                    await self.rebuild_pipeline()
        except Exception as e:
            print(f"[Error] {e}")
    
    async def rebuild_pipeline(self):
        """Rebuild pipeline with new encoder settings."""
        print("[Pipeline] stopping old pipeline...")
        self.pipe.set_state(Gst.State.NULL)
        
        await asyncio.sleep(0.5)
        
        print("[Pipeline] creating new pipeline...")
        self.build_pipeline()
        self.webrtc.connect("on-negotiation-needed", self.on_negotiation)
        self.webrtc.connect("on-ice-candidate", self.on_ice)
        
        self.pipe.set_state(Gst.State.PLAYING)
        self.rebuild_needed = False
    
    def on_negotiation(self, element):
        """Handle negotiation-needed signal."""
        promise = Gst.Promise.new_with_change_func(self.on_offer, None, None)
        element.emit("create-offer", None, promise)
    
    def on_offer(self, promise, *_):
        """Handle offer creation."""
        promise.wait()
        reply = promise.get_reply()
        offer = reply.get_value("offer")
        
        print("[SDP] OFFER created")
        self.webrtc.emit("set-local-description", offer, Gst.Promise.new())
        
        asyncio.run_coroutine_threadsafe(
            self.ws.send(json.dumps({"offer": offer.sdp.as_text()})),
            self.loop
        )
    
    def set_remote(self, sdp):
        """Set remote description."""
        res, msg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp.encode()), msg)
        
        answer = GstWebRTC.WebRTCSessionDescription.new(
            GstWebRTC.WebRTCSDPType.ANSWER, msg)
        
        self.webrtc.emit("set-remote-description", answer, Gst.Promise.new())
        print("[SDP] ANSWER set")
    
    def on_ice(self, _, mline, candidate):
        """Handle ICE candidate."""
        asyncio.run_coroutine_threadsafe(
            self.ws.send(json.dumps({"ice": candidate})),
            self.loop
        )


async def main():
    sender = AdaptiveSender()
    await sender.run()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Adaptive WebRTC Sender")
    print("="*60)
    print(f"Feedback port: {FEEDBACK_PORT}")
    print(f"Signal server: {SIGNAL_SERVER}")
    print(f"Initial profile: 1 (medium)")
    print("\nProfile definitions:")
    for p, cfg in PROFILES.items():
        print(f"  {p}: {cfg['name']} ({cfg['bitrate']} kbps, {cfg['fps']} FPS)")
    print("="*60 + "\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Sender] shutting down...")
