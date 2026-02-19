#!/bin/bash
echo "Starting Rhythm Hero..."
[ ! -d "venv" ] && python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
python3 main.py
