"""
Assignment 3 - Local VM Monitor & AWS Auto-Scale Trigger
Neha Prasad M25AI2056

This script runs on the local VirtualBox VM.
It monitors CPU usage every 10 seconds.
If CPU stays above 75% for 3 consecutive checks (30 seconds),
it automatically launches an EC2 instance on AWS and deploys
the same FastAPI application using a user-data bootstrap script.

Usage:
    python3 monitor_and_scale.py

Prerequisites:
    - AWS CLI configured with credentials (aws configure)
    - boto3 and psutil installed (pip3 install boto3 psutil)
"""

import psutil
import boto3
import time
import os
import sys
import json
from datetime import datetime

# AWS Settings
AWS_REGION = "eu-north-1"
AMI_ID = "ami-0f77cdd9f61b7735e"           # Amazon Linux 2023 (same as Assignment 2)
INSTANCE_TYPE = "t3.micro"                   # Free-tier eligible
KEY_PAIR_NAME = "my-asg-keypair"             # Your existing key pair from Assignment 2
SECURITY_GROUP_ID = "sg-0ddf5f6fd5d4433ee2"   # WebServer-SG from Assignment 2
INSTANCE_NAME = "AutoScale-CloudBurst"       # Tag for the launched instance

# Monitoring Settings
CPU_THRESHOLD = 75          # Percentage - trigger when CPU goes above this
CHECK_INTERVAL = 10         # Seconds between each CPU check
CONSECUTIVE_CHECKS = 3      # Number of consecutive checks above threshold before triggering
                            # So trigger after 30 seconds of sustained high CPU

# Path to the user-data script (relative to this file)
USER_DATA_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                "..", "aws", "user_data.sh")


# State Tracking

class ScalingState:
    """Track whether we've already scaled out to prevent duplicate launches."""
    def __init__(self):
        self.scaled_out = False
        self.ec2_instance_id = None
        self.consecutive_high = 0
        self.launch_time = None

    def reset(self):
        self.consecutive_high = 0

state = ScalingState()

# Logging

def log(message, level="INFO"):
    """Print timestamped log messages."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")


# AWS EC2 Launch


def read_user_data():
    """Read the user-data bootstrap script for EC2."""
    try:
        with open(USER_DATA_SCRIPT, "r") as f:
            return f.read()
    except FileNotFoundError:
        log(f"ERROR: user_data.sh not found at {USER_DATA_SCRIPT}", "ERROR")
        log("Make sure aws/user_data.sh exists in the project directory", "ERROR")
        sys.exit(1)

def launch_ec2_instance():
    """Launch an EC2 instance on AWS with the sample app."""
    log("=" * 60)
    log("THRESHOLD EXCEEDED - LAUNCHING AWS EC2 INSTANCE")
    log("=" * 60)

    try:
        ec2 = boto3.client("ec2", region_name=AWS_REGION)
        
        user_data = read_user_data()
        
        log(f"Region: {AWS_REGION}")
        log(f"AMI: {AMI_ID}")
        log(f"Instance Type: {INSTANCE_TYPE}")
        log(f"Key Pair: {KEY_PAIR_NAME}")
        log(f"Security Group: {SECURITY_GROUP_ID}")
        
        response = ec2.run_instances(
            ImageId=AMI_ID,
            InstanceType=INSTANCE_TYPE,
            KeyName=KEY_PAIR_NAME,
            SecurityGroupIds=[SECURITY_GROUP_ID],
            MinCount=1,
            MaxCount=1,
            UserData=user_data,
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": INSTANCE_NAME},
                        {"Key": "CreatedBy", "Value": "Assignment3-Monitor"},
                        {"Key": "Student", "Value": "M25AI2036"},
                        {"Key": "Purpose", "Value": "Cloud-Burst-AutoScale"}
                    ]
                }
            ]
        )
        
        instance_id = response["Instances"][0]["InstanceId"]
        state.ec2_instance_id = instance_id
        state.scaled_out = True
        state.launch_time = datetime.now()
        
        log(f"EC2 Instance Launched Successfully!")
        log(f"Instance ID: {instance_id}")
        log(f"Launch Time: {state.launch_time.isoformat()}")
        log("")
        log("Waiting for instance to get public IP...")
        
        # Wait for the instance to be running and get its public IP
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])
        
        # Get the public IP
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = desc["Reservations"][0]["Instances"][0].get("PublicIpAddress", "N/A")
        instance_state = desc["Reservations"][0]["Instances"][0]["State"]["Name"]
        
        log(f"Instance State: {instance_state}")
        log(f"Public IP: {public_ip}")
        log(f"App URL: http://{public_ip}:8000")
        log(f"App will be available in ~2-3 minutes (installing dependencies)")
        log("=" * 60)
        
        # Save launch details to a file for the report
        launch_details = {
            "instance_id": instance_id,
            "public_ip": public_ip,
            "ami": AMI_ID,
            "instance_type": INSTANCE_TYPE,
            "region": AWS_REGION,
            "security_group": SECURITY_GROUP_ID,
            "launch_time": state.launch_time.isoformat(),
            "trigger_reason": f"CPU exceeded {CPU_THRESHOLD}% for {CONSECUTIVE_CHECKS * CHECK_INTERVAL} seconds"
        }
        
        details_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "docs", "launch_details.json")
        with open(details_file, "w") as f:
            json.dump(launch_details, f, indent=2)
        log(f"Launch details saved to {details_file}")
        
        return True
        
    except Exception as e:
        log(f"Failed to launch EC2 instance: {str(e)}", "ERROR")
        log("Check your AWS credentials and configuration", "ERROR")
        return False

# Monitoring loop

def get_system_stats():
    """Get current CPU and memory usage."""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024**3), 2),
        "memory_total_gb": round(mem.total / (1024**3), 2)
    }

def monitor():
    """Main monitoring loop."""
    log("=" * 60)
    log("ASSIGNMENT 3 - LOCAL VM RESOURCE MONITOR")
    log("VCC")
    log("=" * 60)
    log(f"CPU Threshold:        {CPU_THRESHOLD}%")
    log(f"Check Interval:       {CHECK_INTERVAL} seconds")
    log(f"Consecutive Checks:   {CONSECUTIVE_CHECKS} (trigger after {CONSECUTIVE_CHECKS * CHECK_INTERVAL}s)")
    log(f"AWS Region:           {AWS_REGION}")
    log(f"Target AMI:           {AMI_ID}")
    log(f"Instance Type:        {INSTANCE_TYPE}")
    log("=" * 60)
    log("Monitoring started. Press Ctrl+C to stop.")
    log("")
    
    check_number = 0
    
    try:
        while True:
            check_number += 1
            stats = get_system_stats()
            
            cpu = stats["cpu_percent"]
            mem = stats["memory_percent"]
            
            # Status indicator
            if cpu > CPU_THRESHOLD:
                status = "HIGH"
                state.consecutive_high += 1
            else:
                status = "OK"
                state.consecutive_high = 0  # Reset counter
            
            # Log current stats
            scaled_status = f" | SCALED OUT: {state.ec2_instance_id}" if state.scaled_out else ""
            log(f"Check #{check_number:04d} | CPU: {cpu:5.1f}% | "
                f"MEM: {mem:5.1f}% | Status: {status} | "
                f"High Count: {state.consecutive_high}/{CONSECUTIVE_CHECKS}"
                f"{scaled_status}")
            
            # Check if we need to scale out
            if (state.consecutive_high >= CONSECUTIVE_CHECKS 
                and not state.scaled_out):
                
                log("")
                log(f"CPU has been above {CPU_THRESHOLD}% for "
                    f"{CONSECUTIVE_CHECKS * CHECK_INTERVAL} seconds!")
                log("Triggering AWS EC2 launch...")
                log("")
                
                success = launch_ec2_instance()
                
                if success:
                    log("")
                    log("Cloud bursting complete. Continuing to monitor...")
                    log("(Will not launch additional instances)")
                    log("")
                else:
                    log("EC2 launch failed. Will retry on next threshold breach.", "WARN")
                    state.consecutive_high = 0  # Reset to allow retry
            
            # Wait before next check
            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        log("")
        log("=" * 60)
        log("Monitoring stopped by user (Ctrl+C)")
        if state.scaled_out:
            log(f"Note: EC2 instance {state.ec2_instance_id} is still running on AWS!")
            log("Remember to terminate it to avoid charges:")
            log(f"  aws ec2 terminate-instances --instance-ids {state.ec2_instance_id}")
        log("=" * 60)



if __name__ == "__main__":
   
    log("Running pre-flight checks...")
    
    # Check if boto3 is configured
    try:
        sts = boto3.client("sts", region_name=AWS_REGION)
        identity = sts.get_caller_identity()
        log(f"AWS Account: {identity['Account']}")
        log(f"AWS User: {identity['Arn']}")
    except Exception as e:
        log(f"AWS credentials not configured: {e}", "ERROR")
        log("Run 'aws configure' first to set up your credentials", "ERROR")
        sys.exit(1)
    
    # Check if user_data.sh exists
    if not os.path.exists(USER_DATA_SCRIPT):
        log(f"user_data.sh not found at: {USER_DATA_SCRIPT}", "ERROR")
        sys.exit(1)
    else:
        log(f"User data script found: {USER_DATA_SCRIPT}")
    
    log("Pre-flight checks passed!")
    log("")
    
    # Start monitoring
    monitor()
