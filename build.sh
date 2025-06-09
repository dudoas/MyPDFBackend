#!/usr/bin/env bash
# Update package lists and install Ghostscript
apt-get update -y && apt-get install -y ghostscript
# Install Python dependencies
pip install -r requirements.txt
