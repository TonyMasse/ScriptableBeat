#!/usr/bin/env bash

# =============================================
# Author:      Tony Massé
# Create date: 2023-09-04
# Description: Initialise the container.
# Parameters:
#  --help         Shows Help message
# =============================================

# To be ran on the Docker host to start this container

# Display Help message
if [[ "$*" == *help* ]]; then
  echo ""
  echo "Usage:  $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "   --help                Shows this help"
  echo ""
  echo "By default (no parameters) it will initialise the container and quit."
  echo ""
  exit 0
fi

echo "### Jump into \`/app/cmd/beats/scriptablebeat/\` directory..."
cd /app/cmd/beats/scriptablebeat/

echo "### COPYING TEMPLATE CONFIGURATION..."
# Make sure the configuration directory exists
mkdir -p /beats/scriptablebeat/config
# Copy the template configuration
cp --no-clobber --recursive config.dist/* /beats/scriptablebeat/config/

# Prepare the state directory
mkdir -p /beats/scriptablebeat/state
