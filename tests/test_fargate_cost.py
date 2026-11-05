from decimal import Decimal
from pathlib import Path

from settlement_recon.fargate_cost import CPU_UNITS, MEMORY_MIB, HourlyRates, monthly_compute


def test_projected_mumbai_compute_uses_binary_memory_units_and_task_hours():
    # The ECS public catalog listed these Linux x86 rates on 2026-10-19.
    rate = HourlyRates(Decimal("0.04256"), Decimal("0.004655"))
    assert monthly_compute(rate, tasks=1, hours=Decimal(730)) == Decimal("9.466275")
    assert monthly_compute(rate, tasks=2, hours=Decimal("0.5")) == Decimal("0.0129675")


def test_cost_profile_matches_the_terraform_task_definition():
    terraform = Path(__file__).resolve().parents[1].joinpath("infra/main.tf").read_text("utf-8")
    task = terraform.split('resource "aws_ecs_task_definition" "app" {', 1)[1]
    settings = dict(line.strip().split("=", 1) for line in task.splitlines()[1:8])
    settings = {key.strip(): value.strip().strip('"') for key, value in settings.items()}
    assert int(settings["cpu"]) == CPU_UNITS
    assert int(settings["memory"]) == MEMORY_MIB
