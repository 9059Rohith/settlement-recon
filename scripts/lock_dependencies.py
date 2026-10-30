"""Pin the complete installed runtime graph plus a separately pinned dev environment.

Uses installed package metadata, including extras, so the lock matches what was tested.
Regenerate in a clean Python3.12 environment after explicit upgrades, then rerun audits.
"""

from importlib.metadata import distribution, distributions
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]
queue = [
    Requirement(line)
    for line in (root / "requirements.in").read_text().splitlines()
    if line and not line.startswith("#")
]
visited = set()
runtime = {}
while queue:
    request = queue.pop()
    name = canonicalize_name(request.name)
    key = (name, tuple(sorted(request.extras)))
    if key in visited:
        continue
    visited.add(key)
    package = distribution(name)
    runtime[name] = package.version
    for item in package.requires or []:
        dependency = Requirement(item)
        if dependency.marker is None or any(
            dependency.marker.evaluate({"extra": extra}) for extra in ["", *request.extras]
        ):
            queue.append(dependency)
header = "# Exact installed graph; regenerate with python scripts/lock_dependencies.py\n"
(root / "requirements.txt").write_text(
    header + "".join(f"{name}=={version}\n" for name, version in sorted(runtime.items()))
)
dev = {canonicalize_name(p.metadata["Name"]): p.version for p in distributions()}
dev.pop("settlement-recon", None)
(root / "requirements-dev.txt").write_text(
    header
    + "".join(f"{name}=={version}\n" for name, version in sorted(dev.items()) if name != "pip")
)
print(f"Pinned {len(runtime)} runtime packages and {len(dev)} development packages.")
