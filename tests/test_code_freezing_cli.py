import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "code-freezing.py"


def run_checker(tmp_path: Path, config_text: str, *extra_args: str) -> subprocess.CompletedProcess:
    config_file = tmp_path / "config.yml"
    config_file.write_text(config_text, encoding="utf-8")
    command = [
        sys.executable,
        str(SCRIPT),
        "--config",
        str(config_file),
        *extra_args,
    ]
    return subprocess.run(command, capture_output=True, text=True)


def test_blocks_when_date_is_inside_freeze_window(tmp_path: Path) -> None:
    config = """
bypass_group:
  - root
freezing_dates:
  Release Freeze:
    from: 2026-04-01
    to: 2026-04-10
"""
    result = run_checker(tmp_path, config, "--date", "2026-04-05", "--user", "mylena")
    assert result.returncode == 1
    assert "blocked due to code freezing period" in result.stderr.lower()


def test_allows_bypass_user_even_during_freeze_window(tmp_path: Path) -> None:
    config = """
bypass_group:
  - mylena
freezing_dates:
  Release Freeze:
    from: 2026-04-01
    to: 2026-04-10
"""
    result = run_checker(tmp_path, config, "--date", "2026-04-05", "--user", "mylena")
    assert result.returncode == 0
    assert "is in bypass group" in result.stderr.lower()


def test_fails_with_missing_required_fields(tmp_path: Path) -> None:
    config = """
bypass_group:
  - mylena
"""
    result = run_checker(tmp_path, config)
    assert result.returncode == 1
    assert "required fields is missing" in result.stderr.lower()


def test_passes_when_no_active_freeze_exists(tmp_path: Path) -> None:
    config = """
bypass_group:
  - root
freezing_dates:
  Past Freeze:
    from: 2025-01-01
    to: 2025-01-02
"""
    result = run_checker(tmp_path, config, "--date", "2026-04-01", "--user", "mylena")
    assert result.returncode == 0
    assert "no active freeze" in result.stderr.lower()
