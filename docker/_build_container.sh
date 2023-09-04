#!/usr/bin/env bash

docker build -t tonymasse/scriptable_beat:v0.1 -t tonymasse/scriptable_beat:latest ./ $@
docker push --all-tags tonymasse/scriptable_beat
