"""Release an existing ECS service using OIDC-provided AWS CLI credentials."""

import json
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def aws(*args):
    result = subprocess.run(
        ["aws", *args, "--output", "json"], check=True, capture_output=True, text=True, timeout=900
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def main():
    cluster, name, image = (os.environ[key] for key in ["ECS_CLUSTER", "ECS_SERVICE", "IMAGE"])
    current = aws("ecs", "describe-services", "--cluster", cluster, "--services", name)
    previous = current["services"][0]["taskDefinition"]
    task = aws("ecs", "describe-task-definition", "--task-definition", previous)["taskDefinition"]
    for field in [
        "taskDefinitionArn",
        "revision",
        "status",
        "requiresAttributes",
        "compatibilities",
        "registeredAt",
        "registeredBy",
        "deregisteredAt",
    ]:
        task.pop(field, None)
    for container in task["containerDefinitions"]:
        if container["name"] == "api":
            container["image"] = image
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "task.json"
        path.write_text(json.dumps(task))
        new = aws("ecs", "register-task-definition", "--cli-input-json", f"file://{path}")
    revision = new["taskDefinition"]["taskDefinitionArn"]
    try:
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            name,
            "--task-definition",
            revision,
        )
        aws("ecs", "wait", "services-stable", "--cluster", cluster, "--services", name)
        final = aws("ecs", "describe-services", "--cluster", cluster, "--services", name)
        if final["services"][0]["taskDefinition"] != revision:
            raise RuntimeError("Deployment circuit breaker rolled back the revision")
        url = os.environ["PUBLIC_URL"]
        if not url.startswith("https://"):
            raise ValueError("PUBLIC_URL must use HTTPS")
        with urllib.request.urlopen(url.rstrip("/") + "/readyz", timeout=15) as response:
            if response.status != 200:
                raise RuntimeError("Readiness failed")
        print(json.dumps({"status": "verified", "revision": revision, "url": url}))
    except Exception:
        aws(
            "ecs",
            "update-service",
            "--cluster",
            cluster,
            "--service",
            name,
            "--task-definition",
            previous,
        )
        raise


if __name__ == "__main__":
    main()
