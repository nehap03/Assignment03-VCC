#!/bin/bash
# ============================================================
# Assignment 03 - EC2 User Data Bootstrap Script
# Neha Prasad M25AI2056
#
# This script runs automatically when the EC2 instance launches.
# It installs Python, FastAPI, and starts the same sample app
# that runs on the local VirtualBox VM.
# ============================================================

set -e  # Exit on any error

# Log everything to a file for debugging
exec > /var/log/assignment3-setup.log 2>&1
echo "=== Assignment 3 EC2 Bootstrap Started: $(date) ==="

# Step 1: System update
echo "[1/6] Updating system packages..."
yum update -y

# Step 2: Install Python 3 and pip
echo "[2/6] Installing Python 3 and pip..."
yum install -y python3 python3-pip

# Step 3: Install Python dependencies
echo "[3/6] Installing FastAPI, Uvicorn, psutil..."
pip3 install fastapi uvicorn psutil

# Step 4: Create the application directory
echo "[4/6] Creating application directory..."
mkdir -p /opt/assignment3/app

# Step 5: Write the FastAPI application
echo "[5/6] Writing FastAPI application..."
cat > /opt/assignment3/app/app.py << 'APPEOF'


from fastapi import FastAPI
import socket
import platform
import psutil
import os
from datetime import datetime

app = FastAPI(title="Assign 03 - Neha Cloud Demo")

def get_environment():
    try:
        import urllib.request
        urllib.request.urlopen("http://169.254.169.254/latest/meta-data/", timeout=1)
        return "AWS EC2"
    except:
        return "Local VirtualBox VM"

ENVIRONMENT = get_environment()

@app.get("/")
def root():
    return {
        "message": f"Hello from {ENVIRONMENT}",
        "hostname": socket.gethostname(),
        "timestamp": datetime.now().isoformat(),
        "environment": ENVIRONMENT
    }

@app.get("/health")
def health():
    return {"status": "healthy", "environment": ENVIRONMENT}

@app.get("/stats")
def stats():
    return {
        "environment": ENVIRONMENT,
        "hostname": socket.gethostname(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
        "disk_percent": psutil.disk_usage('/').percent,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/info")
def info():
    return {
        "course": "VCC",
        "assignment": "Assignment 03 - Hybrid Auto-Scaling",
        "student": "Neha Prasad M25AI2056",
        "description": "This instance was launched automatically when local VM CPU exceeded 75%",
        "environment": ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
APPEOF

# Step 6: Start the application
echo "[6/6] Starting FastAPI application on port 8000..."
cd /opt/assignment3/app
nohup python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 &

echo "=== Assignment 3 EC2 Bootstrap Complete: $(date) ==="
echo "App running at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
