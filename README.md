# Assignment 3 — Adaptive Cloud Bursting: VirtualBox to AWS EC2

**Course:** CSL7510 — Virtualization and Cloud Computing  
**Student:** Neha Prasad (M25AI2056)  
**Instructor:** Prof. Sumit Kalra  

## Overview

This assignment implements an automated **cloud bursting** mechanism. A lightweight Python daemon continuously monitors CPU utilization on a local VirtualBox VM. When the CPU load remains above 75% for a sustained 30-second window, the system automatically provisions an AWS EC2 instance in the Stockholm region (`eu-north-1`) and deploys an identical FastAPI workload there — with zero manual intervention.

## System Design

```
┌──────────────────────────────────────────────────────────────┐
│                     Host Machine (Local)                      │
│                                                               │
│   ┌───────────────────────────────────────────────────────┐   │
│   │              VirtualBox Ubuntu Guest VM               │   │
│   │                                                       │   │
│   │   ┌─────────────────┐   ┌───────────────────────┐    │   │
│   │   │  FastAPI Service │   │   cpu_watchdog.py     │    │   │
│   │   │  0.0.0.0:8000   │   │  polls psutil every   │    │   │
│   │   │                 │   │  10s; 3 consecutive   │    │   │
│   │   │  /        → OK  │   │  readings >75% fires  │    │   │
│   │   │  /health  → UP  │   │  the burst trigger    │    │   │
│   │   │  /metrics → CPU │   └──────────┬────────────┘    │   │
│   │   └─────────────────┘              │                 │   │
│   └────────────────────────────────────┼─────────────────┘   │
└────────────────────────────────────────┼─────────────────────┘
                                         │
                              boto3 EC2 API (HTTPS)
                                         │
                                         ▼
                   ┌─────────────────────────────────────────┐
                   │       AWS eu-north-1 (Stockholm)         │
                   │                                          │
                   │   ┌──────────────────────────────────┐   │
                   │   │     EC2 t3.micro Instance         │   │
                   │   │     Amazon Linux 2023             │   │
                   │   │                                   │   │
                   │   │   cloud-init / user-data:         │   │
                   │   │   → installs Python + FastAPI     │   │
                   │   │   → starts uvicorn on :8000       │   │
                   │   │   → logs to /var/log/burst.log    │   │
                   │   └──────────────────────────────────┘   │
                   └─────────────────────────────────────────┘
```

## Repository Layout

```
assignment3/
├── app/
│   └── app.py                  # FastAPI service (local + cloud)
├── monitor/
│   └── cpu_watchdog.py         # Burst trigger daemon
├── aws/
│   └── cloud_init.sh           # EC2 bootstrap (user-data)
├── docs/
│   └── ec2_launch_record.json  # Written on successful launch
├── requirements.txt
└── README.md
```

---

## Step-by-Step Execution Guide

### Prerequisites (Carried Over from Assignments 1 & 2)

- VirtualBox installed with an Ubuntu VM configured
- Active AWS account with EC2 permissions
- Key pair `my-asg-keypair` already created
- Security group `WebServer-SG` already exists

### STEP 1: Set Up the Local VM Environment

Start your Ubuntu VM in VirtualBox and open a terminal inside it.

```bash
# Refresh package lists and upgrade existing packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip git curl unzip stress

# Create the project directory
mkdir -p ~/assignment3
cd ~/assignment3
# Transfer project files via shared folder, scp, or git clone
```

### STEP 2: Install Python Dependencies

```bash
cd ~/assignment3
pip3 install -r requirements.txt
```

If pip raises an "externally managed environment" warning:
```bash
pip3 install -r requirements.txt --break-system-packages
```

### STEP 3: Configure AWS CLI Inside the VM

```bash
# Download and install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Set up your credentials and target region
aws configure
# Provide:
#   AWS Access Key ID       → your key
#   AWS Secret Access Key   → your secret
#   Default region name     → eu-north-1
#   Default output format   → json

# Confirm the identity resolves correctly
aws sts get-caller-identity
```

### STEP 4: Open Port 8000 on the Security Group

The existing `WebServer-SG` allows HTTP/HTTPS but not port 8000. Add the following rule:

**AWS Console → EC2 → Security Groups → WebServer-SG → Edit Inbound Rules:**

| Type       | Protocol | Port Range | Source    | Description            |
|------------|----------|------------|-----------|------------------------|
| Custom TCP | TCP      | 8000       | 0.0.0.0/0 | FastAPI application    |

Retain all inbound rules already present from Assignment 2.

### STEP 5: Verify Configuration in cpu_watchdog.py

Open `monitor/cpu_watchdog.py` and confirm the constants match your environment:

```python
AWS_REGION      = "eu-north-1"
AMI_ID          = "ami-08eb150f611ca277f"          # Amazon Linux 2023 – eu-north-1
INSTANCE_TYPE   = "t3.micro"
KEY_PAIR_NAME   = "my-asg-keypair"                 # Key pair from Assignment 2
SECURITY_GROUP_ID = "sg-0770a5b0dff337cf7"         # WebServer-SG from Assignment 2
```

### STEP 6: Launch the FastAPI Application Locally

**Terminal 1:**
```bash
cd ~/assignment3/app
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Confirm it is reachable:
```bash
# From a second terminal
curl http://localhost:8000
# Expected: {"message": "Hello from Local VirtualBox VM", ...}

curl http://localhost:8000/metrics
# Returns live CPU and memory statistics
```

**SCREENSHOT 1:** Browser displaying the local FastAPI app at `http://localhost:8000`

### STEP 7: Start the CPU Watchdog

**Terminal 2:**
```bash
cd ~/assignment3/monitor
python3 cpu_watchdog.py
```

Normal output looks like:
```
[2026-03-28 10:00:00] [INFO] Initialising watchdog — running pre-flight checks...
[2026-03-28 10:00:01] [INFO] AWS identity verified: 333650975919
[2026-03-28 10:00:01] [INFO] Pre-flight OK. Entering monitoring loop.
[2026-03-28 10:00:01] [INFO] Poll #0001 | CPU:  2.9% | MEM: 44.7% | Status: NORMAL | Consecutive High: 0/3
[2026-03-28 10:00:11] [INFO] Poll #0002 | CPU:  3.4% | MEM: 44.8% | Status: NORMAL | Consecutive High: 0/3
```

**SCREENSHOT 2:** Watchdog running, showing normal CPU readings

### STEP 8: Simulate High Load to Trigger Cloud Burst

**Terminal 3:**
```bash
# Saturate all vCPUs for 5 minutes
stress --cpu 4 --timeout 300
```

Watch Terminal 2 — after three consecutive high readings the burst fires:
```
[...] Poll #0010 | CPU: 97.3% | MEM: 45.0% | Status: HIGH | Consecutive High: 1/3
[...] Poll #0011 | CPU: 98.8% | MEM: 45.1% | Status: HIGH | Consecutive High: 2/3
[...] Poll #0012 | CPU: 96.5% | MEM: 45.2% | Status: HIGH | Consecutive High: 3/3
[...] Sustained CPU overload detected (>75% for 30 s). Initiating cloud burst...
[...] ============================================================
[...] BURST THRESHOLD REACHED — LAUNCHING EC2 IN eu-north-1
[...] ============================================================
[...] Instance provisioned successfully.
[...] Instance ID : i-0abcdef1234567890
[...] Public IP   : 13.xx.xx.xx
[...] Endpoint    : http://13.xx.xx.xx:8000
```

**SCREENSHOT 3:** Watchdog output showing HIGH status progression and EC2 launch confirmation

### STEP 9: Confirm the Cloud Instance is Serving Traffic

Wait approximately 2–3 minutes for cloud-init to complete, then:

```bash
# Hit the root endpoint on the EC2 instance
curl http://<EC2_PUBLIC_IP>:8000
# Expected: {"message": "Hello from AWS EC2", "environment": "AWS EC2", ...}

curl http://<EC2_PUBLIC_IP>:8000/metrics
# Returns CPU and memory stats from the EC2 instance
```

**SCREENSHOT 4:** Browser confirming `"environment": "AWS EC2"` in the response  
**SCREENSHOT 5:** AWS Console (eu-north-1) showing the new instance tagged `AutoScale-CloudBurst`

### STEP 10: Tear Down Resources

```bash
# Terminate the EC2 instance (avoids unexpected charges)
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>

# Stop the load generator  → Ctrl+C in Terminal 3
# Stop the watchdog        → Ctrl+C in Terminal 2
# Stop the local app       → Ctrl+C in Terminal 1
```

---

## Screenshots Checklist for Report

1. Ubuntu VM running inside VirtualBox
2. FastAPI root endpoint responding on local VM (`localhost:8000`)
3. Watchdog script running with healthy CPU readings
4. `stress` command actively generating CPU load
5. Watchdog detecting sustained >75% and initiating EC2 launch
6. EC2 instance visible in AWS Console (eu-north-1 / Stockholm)
7. FastAPI app responding from EC2 public IP on port 8000
8. Side-by-side comparison: local response shows `"Local VirtualBox VM"`, EC2 response shows `"AWS EC2"`

---

## Course Concepts Illustrated

| Concept | Demonstration in This Assignment |
|---|---|
| Cloud Bursting | Local resource saturation automatically triggers cloud provisioning |
| Rapid Elasticity (NIST) | EC2 instance fully available within minutes of threshold breach |
| On-Demand Self-Service (NIST) | Entire provisioning flow requires no manual steps |
| IaaS Model | AWS supplies raw compute; application layer is fully self-managed |
| Resource Monitoring | `psutil` collects real-time CPU and memory telemetry |
| Infrastructure Automation | `boto3` programmatically manages the full EC2 lifecycle |
| Instance Bootstrapping | `cloud-init` user-data handles all software setup on first boot |

---

## Troubleshooting

**"Unable to locate credentials" or similar AWS auth error**  
→ Run `aws configure` inside the VM; ensure region is set to `eu-north-1`

**EC2 launches but port 8000 times out**  
→ Verify `WebServer-SG` has an inbound TCP rule for port 8000 from `0.0.0.0/0`

**`stress` not found**  
→ Install with `sudo apt install -y stress`

**pip fails with "externally managed environment"**  
→ Append `--break-system-packages` to the pip command

**App on EC2 takes longer than expected to start**  
→ SSH into the instance and inspect the bootstrap log: `sudo cat /var/log/burst.log`