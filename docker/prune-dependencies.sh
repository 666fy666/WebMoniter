#!/bin/sh
# Builder-only pruning. Keep package metadata, licenses and all inference models.
set -eu
find /app/.venv -type d \( -name __pycache__ -o -name tests -o -name test -o -name examples \) -prune -exec rm -rf {} +
find /app/.venv -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*.pyi' -o -name '*.h' -o -name '*.a' \) -delete
# Auditwheel numerical libraries can have alignment-sensitive ELF layouts.
find /app/.venv -type f -name '*.so' \
    ! -path '*.libs/*' ! -path '*/numpy/*' ! -path '*/onnxruntime/*' ! -path '*/cv2/*' \
    -exec strip --strip-unneeded {} +
/app/.venv/bin/python -c 'import aiohttp, uvloop, argon2, cryptography, yaml; from PIL import Image; from Crypto.Cipher import AES'
