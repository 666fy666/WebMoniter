#!/bin/sh
set -eu
umask 077
for dir in "$WEBMONITER_DATA_DIR" "$WEBMONITER_LOG_DIR" "$(dirname "$WEBMONITER_CONFIG_FILE")"; do
  mkdir -p "$dir"
  if [ ! -w "$dir" ]; then
    echo "Directory is not writable by uid $(id -u): $dir" >&2
    exit 1
  fi
done
python -m src.settings.initialize --sample /app/config/config.yml.sample --destination "$WEBMONITER_CONFIG_FILE"
exec python main.py
