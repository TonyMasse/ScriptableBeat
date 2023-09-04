#!/usr/bin/env bash

# Base version
export SCRIPTABLE_BEAT_VERSION=0.1

# Get the latest ubuntu image
docker pull ubuntu:22.04

# Build and ship the container
docker build -t tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION -t tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION.`date --utc +%Y%m%d_%H%M%S` -t tonymasse/scriptable_beat:latest ./ $@
docker push --all-tags tonymasse/scriptable_beat
