# L4S Router Topology - Quick Setup

## Setup
1. On the router VM, verify the router is running and `enp8s0` has DualQ.
2. On the host machine:
   ```bash
   cd /home/alireza/Myprojects/NiCoLE/Topo
   sudo ./setup_topology.sh
   ```
3. Start the topology:
   ```bash
   sudo python3 topo1.py
   ```

## Test connectivity
In the Mininet CLI:

- Same subnet:
  ```bash
  mininet> h0 ping -c 2 h1
  ```
- Router verification:
  ```bash
  mininet> h0 ping -c 2 192.168.200.10
  mininet> h2 ping -c 2 192.168.100.10
  ```

If both cross-subnet pings succeed, the router VM is working correctly.

## Notes
- `h0` and `h1` are on `192.168.100.0/24`.
- `h2` is on `192.168.200.0/24`.
- Router VM IPs are `192.168.100.2` and `192.168.200.2`.
