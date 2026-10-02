"""Installer regressions without changing host packages or contacting platforms."""

import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from ruamel.yaml import YAML

from scripts import bootstrap_source as bootstrap
from src.settings.config import AppConfig, load_config_from_yml
from src.settings.initialize import initialize_config

ROOT = Path(__file__).resolve().parents[2]


def test_initial_configuration_disables_business_and_keeps_comments(tmp_path):
    destination = tmp_path / "config/config.yml"
    assert initialize_config(ROOT / "config/config.yml.sample", destination)
    document = YAML().load(destination)

    def check(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"enable", "enabled", "cookie_refresh_enable"}:
                    assert child is False
                else:
                    check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    assert document.pop("log_cleanup")["enable"] is True
    assert document["push_channel"] == []
    check(document)
    assert "#" in destination.read_text()
    assert destination.stat().st_mode & 0o777 == 0o600
    assert list(destination.parent.iterdir()) == [destination]
    config = AppConfig(**load_config_from_yml(str(destination)))
    assert config.weibo_cookie_refresh_time == "21:00"
    assert config.weibo_chaohua_time == "23:45"


def test_initialization_never_overwrites_existing_config(tmp_path):
    destination = tmp_path / "config.yml"
    original = b"# existing configuration\ncustom: keep-me\n"
    destination.write_bytes(original)
    assert not initialize_config(tmp_path / "missing-sample", destination)
    assert destination.read_bytes() == original


def test_initialization_preserves_concurrent_writer(tmp_path, monkeypatch):
    destination = tmp_path / "config.yml"

    def concurrent_link(source, target):
        target.write_text("concurrent: preserved\n")
        raise FileExistsError

    monkeypatch.setattr(os, "link", concurrent_link)
    assert not initialize_config(ROOT / "config/config.yml.sample", destination)
    assert destination.read_text() == "concurrent: preserved\n"
    assert list(tmp_path.iterdir()) == [destination]


def test_frontend_rebuilds_only_when_inputs_change(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    for name in (
        "package.json",
        "package-lock.json",
        "index.html",
        "vite.config.ts",
        "tsconfig.json",
    ):
        (frontend / name).write_text("initial")
    (frontend / "src").mkdir()
    source = frontend / "src/app.ts"
    source.write_text("initial")
    (frontend / "dist").mkdir()
    (frontend / "dist/index.html").write_text("built")
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    calls = []
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "ensure_node", lambda _: None)
    monkeypatch.setattr(bootstrap, "run", lambda args: calls.append(args))
    bootstrap.build_frontend(runtime)
    assert len(calls) == 2
    bootstrap.build_frontend(runtime)
    assert len(calls) == 2
    source.write_text("changed")
    bootstrap.build_frontend(runtime)
    assert len(calls) == 4
    (frontend / "dist/index.html").unlink()
    bootstrap.build_frontend(runtime)
    assert len(calls) == 6


def test_failed_frontend_build_does_not_cache_success(tmp_path, monkeypatch):
    monkeypatch.setattr(bootstrap, "frontend_fingerprint", lambda _: "new")
    monkeypatch.setattr(bootstrap, "ensure_node", lambda _: None)

    def fail(args):
        raise subprocess.CalledProcessError(1, args)

    monkeypatch.setattr(bootstrap, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        bootstrap.build_frontend(tmp_path)
    assert not (tmp_path / "frontend.sha256").exists()


def test_node_checksum_failure_stops_before_extraction(tmp_path, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bootstrap.platform, "machine", lambda: "x86_64")

    def download(url, destination):
        if destination.name == "SHASUMS256.txt":
            destination.write_text(f"invalid  node-v{bootstrap.NODE_VERSION}-linux-x64.tar.xz\n")
        else:
            destination.write_bytes(b"invalid archive")

    monkeypatch.setattr(bootstrap, "download", download)
    with pytest.raises(RuntimeError, match="校验失败"):
        bootstrap.ensure_node(tmp_path)
    assert not list(tmp_path.iterdir())


def test_custom_browser_requires_both_executables(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROME_BIN", str(tmp_path / "missing"))
    monkeypatch.delenv("CHROMEDRIVER_PATH", raising=False)
    with pytest.raises(RuntimeError, match="同时提供"):
        bootstrap.prepare_browser(tmp_path)


def test_browser_install_and_cached_reuse(tmp_path, monkeypatch):
    monkeypatch.delenv("CHROME_BIN", raising=False)
    monkeypatch.delenv("CHROMEDRIVER_PATH", raising=False)
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Linux")
    monkeypatch.setattr(bootstrap.platform, "machine", lambda: "x86_64")
    downloads = []

    def download(url, destination):
        downloads.append(url)
        names = (
            ["chromedriver-linux64/chromedriver"]
            if destination.name == "chromedriver.zip"
            else ["chrome-linux64/chrome", "chrome-linux64/chrome_crashpad_handler"]
        )
        with zipfile.ZipFile(destination, "w") as bundle:
            for name in names:
                bundle.writestr(name, "fixture")

    monkeypatch.setattr(bootstrap, "download", download)
    monkeypatch.setattr(bootstrap, "install_browser_libraries", lambda _: None)
    monkeypatch.setattr(
        bootstrap, "run", lambda *args, **kwargs: SimpleNamespace(stdout=bootstrap.CHROME_VERSION)
    )
    # Restore environment changes made by the bootstrap function after this test.
    monkeypatch.setenv("CHROME_BIN", "")
    monkeypatch.setenv("CHROMEDRIVER_PATH", "")
    bootstrap.prepare_browser(tmp_path)
    assert len(downloads) == 2
    assert os.access(os.environ["CHROME_BIN"], os.X_OK)
    assert os.access(os.environ["CHROMEDRIVER_PATH"], os.X_OK)
    monkeypatch.delenv("CHROME_BIN")
    monkeypatch.delenv("CHROMEDRIVER_PATH")
    bootstrap.prepare_browser(tmp_path)
    assert len(downloads) == 2


@pytest.mark.parametrize("browser", [False, True])
def test_source_preparation_includes_models_only_for_full(tmp_path, monkeypatch, browser):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(shutil, "which", lambda _: "/mock/uv")
    for name in (
        "PATH",
        "VIRTUAL_ENV",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
    ):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    calls = []
    monkeypatch.setattr(bootstrap, "run", lambda args: calls.append(args))
    monkeypatch.setattr(bootstrap, "build_frontend", lambda _: calls.append(["frontend"]))
    monkeypatch.setattr(bootstrap, "prepare_browser", lambda _: calls.append(["browser"]))
    python = bootstrap.prepare_source(browser=browser)
    assert python == tmp_path / ".venv/bin/python"
    assert [str(python), "-m", "src.settings.initialize"] in calls
    assert (["browser"] in calls) is browser
    assert ([str(python), "src/tasks/ikuuu_models.py"] in calls) is browser


@pytest.mark.parametrize("mode,exit_code", [("docker", 0), ("docker", 17), ("source", 0)])
def test_shell_installer_dispatch_and_failure(tmp_path, mode, exit_code):
    checkout = tmp_path / "checkout with spaces"
    checkout.mkdir()
    shutil.copyfile(ROOT / "install.sh", checkout / "install.sh")
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    captured = tmp_path / "arguments"
    executable = binary_dir / ("docker" if mode == "docker" else "uv")
    executable.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$@" >> "$CAPTURED"\n'
        'if [[ "$*" == *" up "* ]]; then exit "$INSTALL_EXIT"; fi\n'
    )
    executable.chmod(0o755)
    result = subprocess.run(
        [
            "bash",
            str(checkout / "install.sh"),
            mode,
            *(["--prepare-only", "--no-browser"] if mode == "source" else []),
        ],
        env={
            **os.environ,
            "PATH": f"{binary_dir}:{os.environ['PATH']}",
            "CAPTURED": str(captured),
            "INSTALL_EXIT": str(exit_code),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == exit_code
    args = captured.read_text().splitlines()
    if mode == "source":
        assert args == [
            "run",
            "--no-project",
            "--python",
            "3.11",
            "scripts/bootstrap_source.py",
            "--prepare-only",
            "--no-browser",
        ]
    else:
        assert str(checkout / "compose.yaml") in args
        assert "--wait" in args and "always" in args
        assert ("已启动" in result.stdout) is (exit_code == 0)
