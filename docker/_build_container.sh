#!/usr/bin/env bash

# Base version
export SCRIPTABLE_BASE_VERSION=0.1
export SCRIPTABLE_BEAT_VERSION=$SCRIPTABLE_BASE_VERSION.`date --utc +%Y%m%d_%H%M%S`

# Some fancy help message
if [[ "$*" == *help* ]]; then
  echo ""
  echo "Usage: $0 <option>"
  echo ""
  echo "Options:"
  echo "   --help                Shows this help"
  echo "   --no-check            Will not check the container for vulnerabilities"
  echo "   --no-publish          Will not publish container to Docker Hub"
  echo ""
  echo "If no option is provided, the container will be verified for vulnerabilities and published to Docker Hub."
  echo ""
  exit 0
fi

# Check the current directory is the docker directory
if [[ ! -f Dockerfile ]]; then
  echo "This script must be run from the docker directory"
  exit 1
fi

# Make sure `dist`, `dist/docker` and `dist/config.dist` folders exist
mkdir -p ../dist/docker
mkdir -p ../dist/config.dist

# Drop the beat version to the dist folder
echo $SCRIPTABLE_BEAT_VERSION > ../dist/VERSION

# Copy Docker Entrypoint files to the dist/docker folder
cp _entrypoint.* ../dist/docker/

# Get the latest ubuntu image
docker pull ubuntu:22.04

# Build the container
docker build --file ../docker/Dockerfile -t tonymasse/scriptable_beat:v$SCRIPTABLE_BASE_VERSION -t tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION -t tonymasse/scriptable_beat:latest ../dist

# Ship the container
if [[ "$*" == *--no-publish* ]]; then
  echo "⚠️  Skipping container publish"
else
  docker push --all-tags tonymasse/scriptable_beat
fi

# Check for vulnerabilities
if [[ "$*" == *--no-check* ]]; then
  echo "⚠️  Skipping vulnerability check"
else
  echo "Checking for vulnerabilities - Downloading Grype..."
  docker pull anchore/grype:latest
  echo "Checking for vulnerabilities - Running Grype..."
  docker run --rm --volume /var/run/docker.sock:/var/run/docker.sock anchore/grype:latest "tonymasse/scriptable_beat:v$SCRIPTABLE_BEAT_VERSION" --add-cpes-if-none
fi
