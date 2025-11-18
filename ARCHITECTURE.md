# System Architecture

## Network Topology

```
                    ┌──────────────────┐
                    │  Client (h1)     │
                    │  10.0.0.1        │
                    └────────┬─────────┘
                             │
                             │
                    ┌────────▼─────────┐
                    │   Switch (s1)    │
                    │   OpenFlow 1.3   │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐  ┌──▼──────┐  ┌────▼──────────┐
     │  Server h2     │  │ h3      │  │  h4      h5   │
     │  10.0.0.2      │  │10.0.0.3 │  │10.0.0.4 .0.5  │
     └────────────────┘  └─────────┘  └───────────────┘
```

## Load Balancer Architecture

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  Client Request → VIP (10.0.0.100)                     │
│                                                         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Ryu SDN Controller                         │
│              (Running on host)                          │
│              Port: 6653                                 │
└──────────────────────┬──────────────────────────────────┘
                       │ OpenFlow 1.3
                       │ Commands & Flows
                       ▼
┌─────────────────────────────────────────────────────────┐
│              OpenFlow Switch (s1)                       │
│              ┌─────────────────────┐                    │
│              │  Flow Table         │                    │
│              │  Group Table        │                    │
│              └─────────────────────┘                    │
└──────────────────────┬──────────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           │           │           │
           ▼           ▼           ▼
      ┌────────┐  ┌────────┐  ┌────────┐
      │Server 1│  │Server 2│  │Server N│
      └────────┘  └────────┘  └────────┘
```

## Controller Decision Flow

```
                    New Packet Arrives
                           │
                           ▼
                    ┌─────────────┐
                    │ ARP Request?│
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │                     │
               YES                   NO
                │                     │
                ▼                     ▼
          ┌──────────┐        ┌─────────────┐
          │Reply VIP │        │To VIP?      │
          │ARP       │        └──────┬──────┘
          └──────────┘               │
                              ┌──────┴──────┐
                              │             │
                             YES           NO
                              │             │
                              ▼             ▼
                      ┌────────────┐  ┌──────────┐
                      │Select      │  │Reverse   │
                      │Server      │  │NAT       │
                      └─────┬──────┘  └──────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │Install Flow  │
                    │Forward Packet│
                    └──────────────┘
```

## Static SELECT Method

```
┌────────────────────────────────────────┐
│         OpenFlow Group Table           │
│                                        │
│  Group ID: 50                          │
│  Type: SELECT (hash-based)             │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Bucket 1: watch_port=2           │ │
│  │   → NAT to 10.0.0.2              │ │
│  │   → Forward to port 2            │ │
│  ├──────────────────────────────────┤ │
│  │ Bucket 2: watch_port=3           │ │
│  │   → NAT to 10.0.0.3              │ │
│  │   → Forward to port 3            │ │
│  ├──────────────────────────────────┤ │
│  │ Bucket 3: watch_port=4           │ │
│  │   → NAT to 10.0.0.4              │ │
│  │   → Forward to port 4            │ │
│  ├──────────────────────────────────┤ │
│  │ Bucket 4: watch_port=5           │ │
│  │   → NAT to 10.0.0.5              │ │
│  │   → Forward to port 5            │ │
│  └──────────────────────────────────┘ │
│                                        │
│  Hash fields: src_ip, dst_ip,         │
│               src_port, dst_port       │
└────────────────────────────────────────┘
```

## Dynamic DWRS Method

```
Controller maintains:

┌────────────────────────────────────┐
│  Load Tracking                     │
│                                    │
│  Server 1: load = 10               │
│  Server 2: load = 15               │
│  Server 3: load = 8                │
│  Server 4: load = 12               │
└────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Serviceability Calculation        │
│                                    │
│  s1 = 1/10 = 0.10                  │
│  s2 = 1/15 = 0.067                 │
│  s3 = 1/8  = 0.125                 │
│  s4 = 1/12 = 0.083                 │
└────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Cumulative Sum List               │
│                                    │
│  s[1] = 0.10                       │
│  s[2] = 0.10 + 0.067 = 0.167       │
│  s[3] = 0.167 + 0.125 = 0.292      │
│  s[4] = 0.292 + 0.083 = 0.375      │
└────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│  Binary Search Selection           │
│                                    │
│  Random r ∈ [0, 0.375]             │
│  Find index where r ≤ s[i]         │
│  → Selected server                 │
└────────────────────────────────────┘
```

## Hybrid Mode State Machine

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                         ▼
              ┌──────────────────┐
              │  STATIC MODE     │
              │  (SELECT Group)  │
              └────┬────┬────────┘
                   │    │
         δ≥threshold│    │δ<threshold
                   │    │(stay)
                   ▼    │
         ┌─────────────┴────────┐
         │  DYNAMIC MODE        │
         │  (DWRS Algorithm)    │
         └──────────┬───────────┘
                    │
          δ<threshold│
                    ▼
              (back to STATIC)

Where δ = variance of server loads
```

## Packet Flow Example

```
1. Client sends: 10.0.0.1 → 10.0.0.100:80

2. Switch receives packet
   ↓
3. No flow match → PACKET_IN to controller
   ↓
4. Controller selects server (h3: 10.0.0.3)
   ↓
5. Controller installs flow:
   Match: dst_ip=10.0.0.100
   Action: set_field(dst_ip=10.0.0.3)
           set_field(dst_mac=00:00:00:00:00:03)
           output(port 3)
   ↓
6. Controller also installs reverse flow:
   Match: src_ip=10.0.0.3
   Action: set_field(src_ip=10.0.0.100)
           set_field(src_mac=AA:BB:CC:DD:EE:FF)
           output(port 1)
   ↓
7. Subsequent packets match flow → fast path!
```

## Failover Mechanism

```
Normal Operation:
┌────────┐
│Server 1│ ✓ Active
├────────┤
│Server 2│ ✓ Active
├────────┤
│Server 3│ ✓ Active
└────────┘

Port Failure Detected:
┌────────┐
│Server 1│ ✓ Active
├────────┤
│Server 2│ ✗ DOWN (watch_port triggered)
├────────┤
│Server 3│ ✓ Active
└────────┘
           │
           ▼
┌──────────────────────┐
│ OpenFlow removes     │
│ bucket for Server 2  │
│ from group table     │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│ Traffic redistributed│
│ to remaining servers │
│ (Server 1 & 3)       │
└──────────────────────┘
```

## File Structure

```
sthiti-sdn-lb/
│
├── topo.py                    # Network topology definition
├── static_select.py           # Static SELECT group controller
├── static_round_robin.py      # Round-robin controller
├── dynamic_least_load.py      # Least-load controller
├── dynamic_dwrs.py            # DWRS algorithm controller
├── hybrid.py                  # Hybrid static/dynamic controller
│
├── venv/                      # Python virtual environment
│   └── (Ryu and dependencies)
│
├── README.md                  # Main documentation
├── INSTALLATION_GUIDE.md      # Detailed setup guide
├── QUICKSTART.md              # Quick reference
├── TROUBLESHOOTING.md         # Common issues & solutions
├── ARCHITECTURE.md            # This file
│
├── install.sh                 # Automated installer
├── test_setup.sh              # Verify installation
└── run_controller.sh          # Helper to run controllers
```

## Communication Ports

```
┌────────────────────────────────────────┐
│  Ryu Controller (Host Machine)         │
│  Port 6653 (OpenFlow 1.3)              │
└───────────────┬────────────────────────┘
                │
                │ TCP Connection
                │ OpenFlow Protocol
                │
┌───────────────▼────────────────────────┐
│  Mininet Virtual Network               │
│  ┌──────────────────────────────────┐  │
│  │ Switch s1                        │  │
│  │ Management: 127.0.0.1:6653       │  │
│  │ Data Plane: Virtual interfaces   │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌─────────┐  ┌─────────┐            │
│  │ h1      │  │ h2-h5   │            │
│  │ Client  │  │ Servers │            │
│  └─────────┘  └─────────┘            │
└────────────────────────────────────────┘
```

## Data Structures

### Server Information
```python
SERVERS = [
    {"ip": "10.0.0.2", "mac": "00:00:00:00:00:02", "port": 2},
    {"ip": "10.0.0.3", "mac": "00:00:00:00:00:03", "port": 3},
    {"ip": "10.0.0.4", "mac": "00:00:00:00:00:04", "port": 4},
    {"ip": "10.0.0.5", "mac": "00:00:00:00:00:05", "port": 5}
]
```

### Load Tracking (Dynamic Methods)
```python
loads = {
    "10.0.0.2": 10,  # current connections/requests
    "10.0.0.3": 15,
    "10.0.0.4": 8,
    "10.0.0.5": 12
}
```

### Cumulative Serviceability (DWRS)
```python
cumulative = [0.10, 0.167, 0.292, 0.375]
```
