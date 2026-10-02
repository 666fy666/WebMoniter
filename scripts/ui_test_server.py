"""Isolated UI test server: disposable config, no scheduler, no platform requests."""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import uvicorn
    import yaml

    with tempfile.TemporaryDirectory(prefix="webmoniter-ui-") as directory:
        runtime = Path(directory)
        sample = yaml.safe_load((ROOT / "config/config.yml.sample").read_text())
        for section in sample.values():
            if isinstance(section, dict):
                if "enable" in section:
                    section["enable"] = False
                if "enabled" in section:
                    section["enabled"] = False
        sample["push_channel"] = []
        sample["log_cleanup"]["enable"] = True
        (runtime / "config.yml").write_text(yaml.safe_dump(sample, allow_unicode=True))
        os.environ["WEBMONITER_DATA_DIR"] = str(runtime / "data")
        os.environ["WEBMONITER_LOG_DIR"] = str(runtime / "logs")
        os.environ["WEBMONITER_CONFIG_FILE"] = str(runtime / "config.yml")
        os.environ.setdefault("WEBMONITER_ADMIN_PASSWORD", "ui-test-only-password")
        os.chdir(runtime)
        from src.web.app import create_web_app

        uvicorn.run(create_web_app(), host="127.0.0.1", port=8877, access_log=False)


if __name__ == "__main__":
    main()
