# Assignment 3 — Adaptive Cloud Bursting: On-Premise VM Overflow to AWS

**Course:** CSL7510 — Virtualization and Cloud Computing  
**Student:** Neha Prasad M25AI2056  
**Instructor:** Prof. Sumit Kalra  

## Overview

A Python-based resource monitor runs continuously inside a local VirtualBox VM. When CPU utilization stays above 75% for a sustained 30-second window, it automatically provisions an EC2 instance in AWS and deploys an identical FastAPI service there. This is a practical implementation of **cloud bursting** — dynamically extending capacity to the cloud when on-premise compute becomes a bottleneck.

## System Architecture

```
╔══════════════════════════════════════════════════════════════╗
║                     HOST MACHINE (Local)                     ║
║                                                              ║
║  ╔════════════════════════════════════════════════════════╗  ║
║  ║              VirtualBox Ubuntu Guest VM                ║  ║
║  ║                                                        ║  ║
║  ║   ┌─────────────────────┐                              ║  ║
║  ║   │   FastAPI Service   │  ◄── handles local requests  ║  ║
║  ║   │     port :8000      │                              ║  ║
║  ║   └─────────────────────┘                              ║  ║
║  ║                                                        ║  ║
║  ║   ┌─────────────────────────────────────────────────┐  ║  ║
║  ║   │           monitor_and_scale.py                  │  ║  ║
║  ║   │                                                 │  ║  ║
║  ║   │  every 10s → sample CPU via psutil              │  ║  ║
║  ║   │  3 consecutive readings > 75% → burst trigger   │  ║  ║
║  ║   │  calls boto3 → launches EC2 in eu-north-1       │  ║  ║
║  ║   └──────────────────────┬──────────────────────────┘  ║  ║
║  ╚═════════════════════════╪════════════════════════════╝  ║
╚════════════════════════════╪═════════════════════════════════╝
                             │
                    boto3 SDK call (HTTPS)
                             │
                             ▼
          ╔═══════════════════════════════════════╗
          ║   AWS Region: eu-north-1 (Stockholm)  ║
          ║                                       ║
          ║   ┌───────────────────────────────┐   ║
          ║   │     EC2 Instance (t3.micro)   │   ║
          ║   │     Amazon Linux 2023         │   ║
          ║   │                               │   ║
          ║   │  user_data.sh runs at boot:   │   ║
          ║   │  → installs dependencies      │   ║
          ║   │  → pulls FastAPI app code     │   ║
          ║   │  → starts uvicorn :8000       │   ║
          ║   │                               │   ║
          ║   │  tag: AutoScale-CloudBurst    │   ║
          ║   └───────────────────────────────┘   ║
          ╚═══════════════════════════════════════╝
```

## Repository Layout

```
assignment3/
├── app/
│   └── app.py                  # FastAPI service — runs on local VM
├── monitor/
│   └── monitor_and_scale.py    # Resource watcher + cloud burst trigger
├── aws/
│   └── user_data.sh            # EC2 instance bootstrap / init script
├── docs/
│   └── launch_details.json     # Written automatically after EC2 launch
├── requirements.txt
└── README.md
```

---

## End-to-End Setup Guide

### Prerequisites (Carried Over from Assignments 1 & 2)

- VirtualBox with a running Ubuntu VM
- AWS account with EC2 permissions
- Key pair `my-asg-keypair` already created in AWS
- Security group `WebServer-SG` already configured

### STEP 1: Set Up the Ubuntu VM Environment

Start your VirtualBox VM and open a terminal inside it.

```bash
# Refresh package index and upgrade installed packages
sudo apt update && sudo apt upgrade -y

# Install required system tools
sudo apt install -y python3 python3-pip git curl unzip stress
```

Create the project directory structure:

```bash
mkdir -p ~/assignment3/{app,monitor,aws,docs}
cd ~/assignment3
# Transfer your project files here via shared folder, scp, or git clone
```

### STEP 2: Install Python Requirements

```bash
cd ~/assignment3
pip3 install -r requirements.txt
```

> **Note:** If pip returns an "externally managed environment" error, append the flag:
> ```bash
> pip3 install -r requirements.txt --break-system-packages
> ```

### STEP 3: Set Up AWS CLI and Credentials

```bash
# Download and install the AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Provide your IAM credentials
aws configure
# Prompts for:
#   AWS Access Key ID      → your key
#   AWS Secret Access Key  → your secret
#   Default region         → eu-north-1
#   Default output format  → json

# Confirm connectivity
aws sts get-caller-identity
```

### STEP 4: Open Port 8000 in the Security Group

The FastAPI application listens on port 8000. Add this inbound rule to `WebServer-SG`:

**AWS Console → EC2 → Security Groups → WebServer-SG → Edit Inbound Rules**

| Type       | Protocol | Port Range | Source    | Description          |
|------------|----------|------------|-----------|----------------------|
| Custom TCP | TCP      | 8000       | 0.0.0.0/0 | FastAPI service port |

Retain all existing rules inherited from Assignment 2.

### STEP 5: Verify Configuration Values in monitor_and_scale.py

Open `monitor/monitor_and_scale.py` and confirm these constants reflect your environment:

```python
AWS_REGION        = "eu-north-1"
AMI_ID            = "ami-0f77cdd9f61b7735e"      # Amazon Linux 2023, eu-north-1
INSTANCE_TYPE     = "t3.micro"
KEY_PAIR_NAME     = "my-asg-keypair"             # Created in Assignment 2
SECURITY_GROUP_ID = "sg-0ddf5f6fd5d433ee2"       # WebServer-SG from Assignment 2
```

### STEP 6: Launch the Local FastAPI Service

Open **Terminal 1** and start the application server:

```bash
cd ~/assignment3/app
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Confirm the service is reachable:

```bash
# In a second terminal tab
curl http://localhost:8000
# Expected: {"message": "Hello from Local VirtualBox VM", ...}

curl http://localhost:8000/stats
# Returns live CPU and memory readings
```

**SCREENSHOT 1:** Browser open at `http://localhost:8000` showing the local VM response

### STEP 7: Start the Resource Monitor

Open **Terminal 2**:

```bash
cd ~/assignment3/monitor
python3 monitor_and_scale.py
```

Typical startup output:

```
[2026-03-28 10:00:00] [INFO] Running pre-flight checks...
[2026-03-28 10:00:00] [INFO] AWS Account: 854970834116
[2026-03-28 10:00:00] [INFO] Pre-flight checks passed!
[2026-03-28 10:00:01] [INFO] Check #0001 | CPU:  2.9% | MEM: 44.7% | Status: OK | High Count: 0/3
[2026-03-28 10:00:11] [INFO] Check #0002 | CPU:  3.1% | MEM: 44.8% | Status: OK | High Count: 0/3
```

**SCREENSHOT 2:** Monitor output with CPU at idle levels

### STEP 8: Simulate CPU Overload to Trigger Bursting

Open **Terminal 3** and saturate all CPU cores:

```bash
# Spawn 4 stress workers for 5 minutes
stress --cpu 4 --timeout 300
```

Switch back to **Terminal 2** and observe the escalation:

```
[...] Check #0010 | CPU: 97.3% | MEM: 44.9% | Status: HIGH | High Count: 1/3
[...] Check #0011 | CPU: 98.7% | MEM: 45.0% | Status: HIGH | High Count: 2/3
[...] Check #0012 | CPU: 96.4% | MEM: 45.1% | Status: HIGH | High Count: 3/3
[...] CPU sustained above 75% — burst condition met!
[...] Initiating EC2 provisioning in eu-north-1...
[...] ============================================================
[...] THRESHOLD EXCEEDED - LAUNCHING AWS EC2 INSTANCE
[...] ============================================================
[...] EC2 Instance Launched Successfully!
[...] Instance ID: i-0abcdef1234567890
[...] Public IP: 16.xxx.xxx.xxx
[...] App URL: http://16.xxx.xxx.xxx:8000
```

**SCREENSHOT 3:** Monitor output showing sustained HIGH status and the EC2 launch event

### STEP 9: Validate the Cloud-Deployed Service

Allow 2–3 minutes for EC2 bootstrapping to complete, then probe the cloud endpoint:

```bash
curl http://<EC2_PUBLIC_IP>:8000
# Expected: {"message": "Hello from AWS EC2", ...}

curl http://<EC2_PUBLIC_IP>:8000/stats
# Returns EC2 instance resource metrics
```

**SCREENSHOT 4:** Browser showing the FastAPI response from EC2 with `"environment": "AWS EC2"`  
**SCREENSHOT 5:** AWS Console EC2 dashboard showing the new instance tagged `AutoScale-CloudBurst`

### STEP 10: Tear Down Resources

```bash
# Terminate the EC2 instance to stop billing
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>

# Stop the stress load generator  → Ctrl+C in Terminal 3
# Stop the monitoring script      → Ctrl+C in Terminal 2
# Stop the local FastAPI server   → Ctrl+C in Terminal 1
```

---

## Screenshots Checklist for Report

1. VirtualBox showing the Ubuntu VM running
2. FastAPI responding at `http://localhost:8000` on the local VM
3. Monitoring script active with CPU at normal levels
4. `stress` tool running and pegging CPU usage
5. Monitor detecting sustained overload and triggering the EC2 launch
6. New EC2 instance visible in the AWS Console (eu-north-1 region)
7. FastAPI responding from the EC2 public IP on port 8000
8. Side-by-side comparison: local response reads "Local VirtualBox VM" vs EC2 response reads "AWS EC2"

---

## Cloud Computing Concepts Covered

| Concept | Demonstration in This Assignment |
|---|---|
| Cloud Bursting | Excess local load is automatically shifted to EC2 |
| Rapid Elasticity | New compute instance ready within minutes |
| On-Demand Self-Service | No manual cloud interaction — fully scripted |
| Infrastructure as a Service | AWS provides bare VM; OS and app are self-managed |
| Real-Time Monitoring | `psutil` samples CPU and memory every 10 seconds |
| Programmatic Provisioning | `boto3` handles EC2 lifecycle without the console |
| Instance Bootstrap | `user_data.sh` self-configures EC2 at first boot |

---

## Troubleshooting Reference

**"Unable to locate credentials" error**  
→ AWS CLI is not configured. Run `aws configure` and supply your Access Key ID, Secret Key, and set region to `eu-north-1`.

**EC2 instance is running but port 8000 is unreachable**  
→ The security group `WebServer-SG` is missing the inbound TCP rule for port 8000. Add it as shown in Step 4.

**`stress` command not found**  
→ Run `sudo apt install -y stress` inside the VM.

**`pip install` fails with "externally managed environment"**  
→ Append `--break-system-packages` to the install command.

**App not yet available shortly after EC2 launch**  
→ Bootstrap is still running. SSH into the instance and tail the log:
```bash
cat /var/log/assignment3-setup.log
```