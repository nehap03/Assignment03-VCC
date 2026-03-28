"""
Assignment 3 - Test FastAPI Microservice
Neha Prasad M25AI2056
"""

from fastapi import FastAPI
import socket
import platform
import psutil
import os
from datetime import datetime

app = FastAPI(title="Assign 03 - Neha Cloud Demo")

# Detect environment: check if running on EC2 or local VM
def get_environment():
    """Detect whether we are on local VirtualBox VM or AWS EC2."""
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
    """Show current resource usage - useful for demo screenshots."""
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
    """Assignment metadata for the report."""
    return {
        "course": "VCC",
        "assignment": "Assignment 03 Hybrid Auto-Scaling",
        "student": "Neha Prasad M25AI2056",
        "description": "Local VM monitors CPU; when usage > 75%, "
                       "automatically launches EC2 instance with same app.",
        "environment": ENVIRONMENT
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
