#!/usr/bin/env bash

# =============================================
# Author:      Tony Massé
# Create date: 2023-09-04
# Description: Call Init then run the container.
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
  echo "By default (no parameters) it will run for ever."
  echo ""
  exit 0
fi

echo "### Run \`Init\` entry point..."
/app/cmd/beats/scriptablebeat/docker/_entrypoint.init.sh

echo ""
echo "#########################################################"
echo "##                                                     ##"
echo "##                   CONTAINER READY                   ##"
echo "##                                                     ##"
echo "#########################################################"
echo ""

# TODO: Replace this with the actual command to run
tail -f /dev/null