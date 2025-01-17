#!/bin/bash

# Define the name of the virtual environment
ENV_NAME="venv"

# Create virtual environment
python3 -m venv $ENV_NAME

# Activate virtual environment
source $ENV_NAME/bin/activate

# Check if requirements.txt exists and install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt does not exist."
fi

echo "Setup completed. Virtual environment '$ENV_NAME' is activated."
