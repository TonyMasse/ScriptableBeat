#!/usr/bin/env bash

# Build (without publishing, not checking), run the container, Shell into it, then remove it
# ./_build_container.sh --no-publish --no-check && docker run -d --name sb tonymasse/scriptable_beat:latest && docker exec -it sb bash && docker rm sb --force

# ./_build_container.sh --no-publish --no-check && \
# docker run --detach --name sb --volume "/root/sb_dev/ScriptableBeat/config.dev/scriptablebeat.yml":"/beats/scriptablebeat/config/scriptablebeat.yml":ro tonymasse/scriptable_beat:latest && \
# docker exec -it sb bash && docker rm sb --force

./_build_container.sh --no-publish --no-check && \
docker run --detach --name sb --volume "/var/lib/docker/volumes/sb_dev/_data/ScriptableBeat/config.dev/scriptablebeat.yml":"/beats/scriptablebeat/config/scriptablebeat.yml":ro tonymasse/scriptable_beat:latest && \
docker exec -it sb bash && docker rm sb --force
