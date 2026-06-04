#!/bin/sh
set -e
# 确保 data / logs 存在且可写（兼容首次启动与 bind mount 权限）
for dir in /app/data /app/logs; do
  mkdir -p "$dir"
  chmod -R 777 "$dir" 2>/dev/null || true
done
exec python main.py
