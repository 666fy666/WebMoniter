"""Measure Docker save layers using one consistent compressed/unpacked byte basis."""

import argparse
import json
import subprocess
import tarfile
import zlib
from pathlib import Path


def measure(image):
    process = subprocess.Popen(["docker", "image", "save", image], stdout=subprocess.PIPE)
    blobs, manifests = {}, []
    with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for entry in archive:
            if not entry.isfile():
                continue
            stream = archive.extractfile(entry)
            if entry.size < 128 * 1024 and (
                entry.name.endswith(".json") or "/sha256/" in entry.name
            ):
                data = stream.read()
                try:
                    record = json.loads(data)
                except (ValueError, UnicodeError):
                    record = None
                if isinstance(record, dict) and "layers" in record:
                    manifests.append(record)
                if record is not None:
                    continue
                chunks = [data]
            else:
                chunks = []
            head = chunks.pop() if chunks else stream.read(1024 * 1024)
            compressed = head.startswith(b"\x1f\x8b")
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if compressed else None
            size = 0
            block = head
            while block:
                size += len(decoder.decompress(block)) if decoder else len(block)
                block = stream.read(1024 * 1024)
            if decoder:
                size += len(decoder.flush())
            blobs[entry.name.split("/")[-1]] = {"stored_bytes": entry.size, "unpacked_bytes": size}
    if process.wait() != 0:
        raise RuntimeError("docker save failed")
    layers = next(
        (
            m["layers"]
            for m in manifests
            if m.get("schemaVersion") == 2
            and all("tar" in layer.get("mediaType", "") for layer in m["layers"])
        ),
        None,
    )
    if layers is None:
        raise RuntimeError("OCI layer manifest missing; use Docker with containerd image store")
    rows = [{**blobs[layer["digest"].split(":")[1]], "digest": layer["digest"]} for layer in layers]
    metadata = json.loads(subprocess.check_output(["docker", "image", "inspect", image]))[0]
    return {
        "image": image,
        "architecture": metadata["Architecture"],
        "id": metadata["Id"],
        "compressed_layer_bytes": sum(row["stored_bytes"] for row in rows),
        "unpacked_layer_bytes": sum(row["unpacked_bytes"] for row in rows),
        "layers": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("images", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = [measure(image) for image in args.images]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps(
            [{key: value for key, value in row.items() if key != "layers"} for row in results],
            indent=2,
        )
    )
