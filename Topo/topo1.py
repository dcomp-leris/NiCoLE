#!/usr/bin/env python3
"""
L4S Router Topology for NiCoLE
===============================
Topology:
  h0 (192.168.100.10/24) \
  h1 (192.168.100.11/24) -- L4S Router (enp7s0: 192.168.100.2, enp8s0: 192.168.200.2)
  h2 (192.168.200.10/24) /

h2 is the bottleneck client connected to the DualQ-equipped interface (enp8s0)
"""

from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info
import os, time, subprocess

ROUTER_IP_100 = "192.168.100.2"  # enp7s0
ROUTER_IP_200 = "192.168.200.2"  # enp8s0

def setup_bridges():
    """Create and setup Linux bridges for router connectivity"""
    info("Setting up bridges for L4S router connection...\n")
    
    # Create bridges if they don't exist
    for br in ["mnbr0", "mnbr1"]:
        result = subprocess.run(f"ip link show {br}", shell=True, capture_output=True)
        if result.returncode != 0:
            info(f"Creating bridge {br}...\n")
            os.system(f"ip link add {br} type bridge")
            os.system(f"ip link set {br} up")
        else:
            info(f"Bridge {br} already exists\n")

def attach(host, bridge, ip, gw, name):
    """Attach mininet host to a bridge with veth pair"""
    host_if = f"{name}-eth0"
    br_if = f"{name}-br"

    os.system(f"ip link add {host_if} type veth peer name {br_if}")
    os.system(f"ip link set {host_if} netns {host.pid}")
    os.system(f"ip link set {br_if} master {bridge}")
    os.system(f"ip link set {br_if} up")

    time.sleep(0.2)

    host.cmd(f"ip addr add {ip} dev {host_if}")
    host.cmd(f"ip link set {host_if} up")
    host.cmd(f"ip route add default via {gw}")
    
    info(f"Attached {name}: {ip} -> {gw}\n")

def main():
    setup_bridges()
    
    net = Mininet(controller=None)

    info("Creating mininet hosts...\n")
    h0 = net.addHost("h0")
    h1 = net.addHost("h1")
    h2 = net.addHost("h2")

    net.start()

    info("Attaching hosts to bridges...\n")
    attach(h0, "mnbr0", "192.168.100.10/24", ROUTER_IP_100, "h0")
    attach(h1, "mnbr0", "192.168.100.11/24", ROUTER_IP_100, "h1")
    attach(h2, "mnbr1", "192.168.200.10/24", ROUTER_IP_200, "h2")

    print("\n" + "="*60)
    print("L4S ROUTER TOPOLOGY READY")
    print("="*60)
    print("\nNetwork Configuration:")
    print("  Subnet 1 (enp7s0): 192.168.100.0/24")
    print("    - h0: 192.168.100.10")
    print("    - h1: 192.168.100.11")
    print("    - Router: 192.168.100.2")
    print("\n  Subnet 2 (enp8s0): 192.168.200.0/24")
    print("    - h2: 192.168.200.10")
    print("    - Router: 192.168.200.2 (with DualQ)")
    print("\nBasic Tests:")
    print("  h0 ping h1              # Same subnet")
    print("  h0 ping 192.168.200.10  # Through router to h2")
    print("  h2 ping 192.168.100.10  # Through router to h0")
    print("\nAdvanced Tests:")
    print("  h0 iperf -s             # Start server on h0")
    print("  h2 iperf -c 192.168.100.10 -t 30  # Connect from h2")
    print("="*60 + "\n")
    
    CLI(net)
    net.stop()

if __name__ == "__main__":
    setLogLevel("info")
    main()
