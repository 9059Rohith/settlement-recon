"""Fail-closed release-build checks; receipts describe executed checks, not GitHub runs."""

import hashlib
import json
import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path


class VerificationFailed(RuntimeError):
    pass


def isolated_environment():
    values = dict(os.environ)
    for key in list(values):
        upper = key.upper()
        if (
            any(part in upper for part in ("SECRET", "TOKEN", "PASSWORD", "CREDENTIAL", "API_KEY"))
            or upper.endswith("_DSN")
            or upper in {"DATABASE_URL", "TEST_DATABASE_URL", "API_TOKEN", "READ_TOKEN"}
            or upper.startswith(("AWS_", "VERCEL", "NEON_", "PG"))
        ):
            values.pop(key, None)
    values.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        AWS_EC2_METADATA_DISABLED="true",
    )
    return values


def run_steps(root, steps):
    results = []
    for name, arguments in steps:
        print(f"BUILD_VERIFY {name}", flush=True)
        try:
            process = subprocess.run(
                arguments, cwd=root, env=isolated_environment(), timeout=360, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise VerificationFailed(f"{name}: {type(error).__name__}") from None
        results.append({"name": name, "exit_code": process.returncode})
        if process.returncode != 0:
            raise VerificationFailed(f"{name} failed with exit code {process.returncode}")
    return results


def junit_counts(path):
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except (OSError, ET.ParseError) as error:
        raise VerificationFailed(f"JUnit unavailable: {type(error).__name__}") from None
    counts = {"passed": 0, "skipped": 0, "failures": 0, "errors": 0, "cases": len(cases)}
    for case in cases:
        if case.find("failure") is not None:
            counts["failures"] += 1
        elif case.find("error") is not None:
            counts["errors"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    if counts["passed"] == 0 or counts["failures"] or counts["errors"]:
        raise VerificationFailed("JUnit does not establish passing executed tests")
    return counts


def source_fingerprint(root):
    root = Path(root).resolve()
    candidates = []
    for name in ("src", "tests", "scripts", "dags"):
        directory = root / name
        if directory.exists():
            candidates.extend(path for path in directory.rglob("*") if path.is_file())
    candidates.extend(root.glob("requirements*.txt"))
    candidates.extend(
        path for path in (root / "pyproject.toml", root / "infra/main.tf") if path.exists()
    )
    digest = hashlib.sha256()
    included = 0
    for path in sorted(candidates):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise VerificationFailed("Source fingerprint refuses external/symlink files")
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        with path.open("rb") as stream:
            digest.update(hashlib.file_digest(stream, "sha256").digest())
        included += 1
    if not included:
        raise VerificationFailed("No source files were fingerprinted")
    return {"sha256": digest.hexdigest(), "files": included}


def main():
    root = Path(__file__).resolve().parents[1]
    output = Path(os.getenv("SETTLEMENT_BUILD_REPORT_DIR", "/tmp/settlement-build-proof"))
    output.mkdir(parents=True, exist_ok=True)
    before = source_fingerprint(root)
    checks = run_steps(
        root,
        [
            ("ruff-check", [sys.executable, "-m", "ruff", "check", "."]),
            ("ruff-format", [sys.executable, "-m", "ruff", "format", "--check", "."]),
            ("bandit-medium-high", [sys.executable, "-m", "bandit", "-r", "src", "-ll", "-q"]),
            (
                "pytest-default",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-p",
                    "anyio.pytest_plugin",
                    "tests",
                    "-q",
                    "-ra",
                    f"--junitxml={output / 'junit.xml'}",
                ],
            ),
        ],
    )
    counts = junit_counts(output / "junit.xml")
    if source_fingerprint(root) != before:
        raise VerificationFailed("Checks modified source inputs")
    receipt = {
        "schema_version": 1,
        "status": "passed",
        "provider": "release-container-build",
        "verified_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "source": before,
        "checks": checks,
        "tests": counts,
        "scope": (
            "Default isolated tests; optional PostgreSQL/S3 integrations are skipped. "
            "Not a GitHub Actions or AWS deployment claim."
        ),
    }
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("BUILD_VERIFY_RECEIPT " + json.dumps(receipt), flush=True)


if __name__ == "__main__":
    try:
        main()
    except VerificationFailed as error:
        print(f"BUILD_VERIFY_FAILED {error}", file=sys.stderr)
        raise SystemExit(1) from None
