#!/usr/bin/env bash

# Base version
export SCRIPTABLE_BASE_VERSION=0.1
export SCRIPTABLE_BEAT_VERSION=$SCRIPTABLE_BASE_VERSION.`date --utc +%Y%m%d_%H%M%S`

# Make sure `dist` folder exists
mkdir -p ../dist

# Drop the beat version to the dist folder
echo $SCRIPTABLE_BEAT_VERSION > ../dist/VERSION

# Get the latest ubuntu image
docker pull ubuntu:22.04

# Go to the build directory
cd ../dist

# Build and ship the container
docker build --file ../docker/Dockerfile -t tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION -t tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION.`date --utc +%Y%m%d_%H%M%S` -t tonymasse/scriptable_beat:latest ./ $@
docker push --all-tags tonymasse/scriptable_beat

# Get back home
cd ../docker
