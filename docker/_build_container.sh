#!/usr/bin/env bash

# Get the latest ubuntu image
docker pull ubuntu:latest

# Build and ship the container
docker build -t tonymasse/scriptable_beat:v0.1 -t tonymasse/scriptable_beat:latest ./ $@
docker push --all-tags tonymasse/scriptable_beat
