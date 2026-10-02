"""Exercise release/check shell guards without contacting GitHub or a registry."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


@pytest.mark.parametrize(
    "changes,code,backend,frontend,success",
    [
        ("success", "true", "success", "success", True),
        ("success", "false", "skipped", "skipped", True),
        ("failure", "false", "skipped", "skipped", False),
        ("cancelled", "", "skipped", "skipped", False),
        ("success", "true", "failure", "success", False),
        ("success", "true", "success", "failure", False),
        ("success", "true", "skipped", "success", False),
        ("success", "true", "success", "cancelled", False),
    ],
)
def test_required_check_gate(changes, code, backend, frontend, success):
    script = workflow("quality.yml")["jobs"]["checks"]["steps"][0]["run"]
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        env={
            **os.environ,
            "CHANGES_RESULT": changes,
            "CODE_CHANGED": code,
            "BACKEND_RESULT": backend,
            "FRONTEND_RESULT": frontend,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is success


@pytest.mark.parametrize(
    "digests,architectures,success",
    [
        (["a" * 64, "b" * 64], ["arm64", "amd64"], True),
        ([], ["amd64", "arm64"], False),
        (["a" * 64], ["amd64", "arm64"], False),
        (["a" * 64, "b" * 64, "c" * 64], ["amd64", "arm64"], False),
        (["a" * 64, "invalid"], ["amd64", "arm64"], False),
        (["a" * 64, "b" * 64], ["amd64"], False),
    ],
)
def test_manifest_publish_guard(tmp_path, digests, architectures, success):
    jobs = workflow("docker-build-push.yml")["jobs"]
    assert set(jobs["publish"]["needs"]) == {"validate", "build"}
    script = jobs["publish"]["steps"][-1]["run"]
    directory = tmp_path / "digests"
    directory.mkdir()
    for digest in digests:
        (directory / digest).touch()
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    calls = tmp_path / "calls"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {"manifests": [{"platform": {"os": "linux", "architecture": a}} for a in architectures]}
        )
    )
    docker = binary_dir / "docker"
    docker.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALLS"\n'
        'if [ "$3" = inspect ]; then cat "$MANIFEST"; fi\n'
    )
    docker.chmod(0o755)
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
        cwd=directory,
        env={
            **os.environ,
            "PATH": f"{binary_dir}:{os.environ['PATH']}",
            "CALLS": str(calls),
            "MANIFEST": str(manifest),
            "IMAGE": "example/webmoniter",
            "TAGS": "example/webmoniter:latest\nexample/webmoniter:2.5.1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is success, result.stderr
    if success:
        commands = calls.read_text().splitlines()
        assert len(commands) == 3
        assert "--tag example/webmoniter:latest --tag example/webmoniter:2.5.1" in commands[0]
        for digest in digests:
            assert f"example/webmoniter@sha256:{digest}" in commands[0]
    elif len(digests) != 2 or "invalid" in digests:
        assert not calls.exists(), "Invalid digests must never reach the registry"
