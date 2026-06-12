"""青龙 CLI smoke 测试。"""

import subprocess
import sys


def test_ql_list_includes_ikuuu_checkin() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "src.ql", "--list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ikuuu_checkin" in result.stdout
