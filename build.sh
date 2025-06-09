#!/usr/bin/env bash

# Install Ghostscript
sudo apt-get update
sudo apt-get install -y ghostscript

# Proceed with standard Python build process (installing dependencies from requirements.txt)
pip install -r requirements.txt
