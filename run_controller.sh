#!/bin/bash
# Start the Ryu controller with the hybrid load balancer
source venv/bin/activate
ryu-manager --verbose hybrid.py
