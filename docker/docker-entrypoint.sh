#!/bin/sh
set -e
# 确保 data / logs 在容器内可写（兼容 bind mount 权限）
for dir in /app/data /app/logs; do
  if [ -d "$dir" ]; then
    chmod -R 777 "$dir"
  fi
done
exec python main.py
