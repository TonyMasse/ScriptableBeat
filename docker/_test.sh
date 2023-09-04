#!/usr/bin/env bash

# Build (without publishing, not checking), run the container, Shell into it, then remove it
./_build_container.sh --no-publish --no-check && docker run -d --name sb tonymasse/scriptable_beat:latest && docker exec -it sb bash && docker rm sb --force
