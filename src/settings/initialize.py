"""Shared first-run configuration for source and container deployments."""

import argparse
import os
import tempfile
from pathlib import Path

from ruamel.yaml import YAML


def initialize_config(sample: Path, destination: Path) -> bool:
    if destination.exists():
        return False
    yaml = YAML()
    yaml.preserve_quotes = True
    document = yaml.load(sample.read_text(encoding="utf-8"))

    def disable(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"enable", "enabled", "cookie_refresh_enable"}:
                    value[key] = False
                else:
                    disable(child)
        elif isinstance(value, list):
            for child in value:
                disable(child)

    disable(document)
    document["push_channel"] = []
    document["log_cleanup"]["enable"] = True
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            yaml.dump(document, stream)
            stream.flush()
            os.fsync(stream.fileno())
        # Atomic creation without overwriting a configuration created concurrently.
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return False
        return True
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=Path("config/config.yml.sample"))
    parser.add_argument(
        "--destination",
        type=Path,
        default=Path(os.environ.get("WEBMONITER_CONFIG_FILE", "config.yml")),
    )
    arguments = parser.parse_args()
    initialize_config(arguments.sample, arguments.destination)
