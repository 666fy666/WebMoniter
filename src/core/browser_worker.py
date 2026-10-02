"""Private IPC entry point. Only explicitly listed operations may execute."""

import contextlib
import json
import sys


def main() -> None:
    request = json.loads(sys.stdin.buffer.read(1024 * 1024))
    try:
        with contextlib.redirect_stdout(sys.stderr):
            payload = request["payload"]
            if request["operation"] == "ikuuu_login":
                from src.tasks.ikuuu_checkin import CheckinConfig, _login_and_get_cookie_sync

                result = _login_and_get_cookie_sync(CheckinConfig(**payload))
            elif request["operation"] == "rainyun_account":
                from src.tasks.rainyun.config_adapter import RainyunAccountConfig
                from src.tasks.rainyun.runner import run_single_account

                result = run_single_account(
                    RainyunAccountConfig(**payload["account"]), **payload["overrides"]
                )
            elif request["operation"] == "weibo_cookie":
                from dataclasses import asdict

                from src.tasks.weibo_cookie_refresh import (
                    CookieValidationRequirements,
                    _renew_cookie_sync,
                )

                result = asdict(
                    _renew_cookie_sync(
                        payload["cookie"],
                        CookieValidationRequirements(**payload["requirements"]),
                        payload["validation_uid"],
                    )
                )
            else:
                raise ValueError("Unknown operation")
        reply = {"ok": True, "result": result}
    except Exception as exc:
        reply = {"ok": False, "kind": type(exc).__name__}
    sys.stdout.write(json.dumps(reply))


if __name__ == "__main__":
    main()
