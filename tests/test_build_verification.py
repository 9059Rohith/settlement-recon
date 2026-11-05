"""Build gates execute real commands and reject missing or unsuccessful evidence."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


def gate():
    path = Path(__file__).resolve().parents[1] / "scripts/build_verify.py"
    spec = importlib.util.spec_from_file_location("settlement_build_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failed_check_stops_later_commands(tmp_path):
    module = gate()
    marker = tmp_path / "must-not-exist"
    steps = [
        ("fail", [sys.executable, "-c", "raise SystemExit(7)"]),
        (
            "later",
            [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
        ),
    ]
    with pytest.raises(module.VerificationFailed, match="fail"):
        module.run_steps(tmp_path, steps)
    assert not marker.exists()


def test_receipt_uses_actual_pytest_counts(tmp_path):
    module = gate()
    test = tmp_path / "test_tiny.py"
    test.write_text(
        "import pytest\ndef test_ok(): assert 2+2==4\n"
        "def test_skip(): pytest.skip('intentional')\n",
        encoding="utf-8",
    )
    junit = tmp_path / "junit.xml"
    subprocess.run(
        [sys.executable, "-m", "pytest", str(test), "-q", f"--junitxml={junit}"],
        cwd=tmp_path,
        check=True,
    )
    counts = module.junit_counts(junit)
    assert counts == {"passed": 1, "skipped": 1, "failures": 0, "errors": 0, "cases": 2}


@pytest.mark.parametrize(
    "body",
    [
        "<testsuite><testcase><failure>bad</failure></testcase></testsuite>",
        "<testsuite><testcase><error>bad</error></testcase></testsuite>",
        "<testsuite><testcase><skipped/></testcase></testsuite>",
        "<testsuite/>",
    ],
)
def test_unusable_junit_cannot_be_a_success(body, tmp_path):
    module = gate()
    path = tmp_path / "junit.xml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(module.VerificationFailed):
        module.junit_counts(path)


def test_source_fingerprint_covers_code_and_ignores_generated_cache(tmp_path):
    module = gate()
    source = tmp_path / "src"
    source.mkdir()
    file = source / "worker.py"
    file.write_text("value=1\n")
    first = module.source_fingerprint(tmp_path)
    cache = source / "__pycache__"
    cache.mkdir()
    (cache / "worker.pyc").write_bytes(b"generated")
    assert module.source_fingerprint(tmp_path) == first
    file.write_text("value=2\n")
    assert module.source_fingerprint(tmp_path) != first
