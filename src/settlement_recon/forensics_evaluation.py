"""Controlled allocation experiments; labels never enter the investigation engine."""

import math
import platform
import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from settlement_recon.forensics import analyze, digest


@dataclass(frozen=True)
class Scenario:
    name: str
    request: dict
    truth: dict[str, list[str] | None]
    interpretation: str


def claim(identity, amount, currency="USD", reference=None):
    return {
        "payment_id": identity,
        "currency": currency,
        "amount_minor": amount,
        "expected_on": "2026-10-29",
        "reference": reference,
    }


def bank(identity, amount, currency="USD", reference=None):
    return {
        "leg_id": identity,
        "currency": currency,
        "net_minor": amount - 1,
        "fee_minor": 1,
        "settled_on": "2026-10-30",
        "reference": reference,
    }


def scenarios(seed):
    generator = random.Random(seed)
    prefix = f"r{generator.randrange(1_000_000)}"
    payments, legs, truth = [], [], {}
    for index in range(4):
        identity, reference = f"p{index}", f"{prefix}-invoice-{index}"
        amount = 1000 + index * 131 + generator.randrange(50)
        currency = generator.choice(["USD", "EUR", "INR", "JPY"])
        payments.append(claim(identity, amount, currency, reference))
        legs.append(bank(f"l{index}", amount, currency, reference))
        truth[identity] = [f"l{index}"]
    yield Scenario(
        "referenced_exact",
        {"payments": payments, "legs": legs},
        truth,
        "Distinct references and integer amounts identify one complete allocation.",
    )
    payments, legs, truth = [], [], {}
    for index in range(3):
        amount = 1500 + generator.randrange(200)
        reference = f"{prefix}-split-{index}"
        first = generator.randrange(400, 700)
        payments.append(claim(f"p{index}", amount, reference=reference))
        legs.extend(
            [
                bank(f"l{index}a", first, reference=reference),
                bank(f"l{index}b", amount - first, reference=reference),
            ]
        )
        truth[f"p{index}"] = [f"l{index}a", f"l{index}b"]
    yield Scenario(
        "referenced_splits",
        {"payments": payments, "legs": legs},
        truth,
        "Two bank legs, including their fees, satisfy one referenced obligation.",
    )
    amount = generator.randrange(1000, 2000)
    yield Scenario(
        "amount_collision",
        {
            "payments": [claim("a", amount), claim("b", amount)],
            "legs": [bank("x", amount), bank("y", amount)],
        },
        {"a": ["x"], "b": ["y"]},
        "Hidden true identities cannot be inferred from equal submitted evidence; abstain.",
    )
    yield Scenario(
        "missing_obligation",
        {"payments": [claim("a", amount), claim("b", amount + 1)], "legs": []},
        {"a": None, "b": None},
        "No settlement evidence exists.",
    )
    yield Scenario(
        "cross_currency",
        {
            "payments": [claim("a", amount, "USD"), claim("b", amount, "EUR")],
            "legs": [bank("x", amount, "EUR"), bank("y", amount, "USD")],
        },
        {"a": ["y"], "b": ["x"]},
        "Equal numeric values in different currencies cannot cross.",
    )
    yield Scenario(
        "reference_conflict",
        {
            "payments": [claim("a", amount, reference=f"{prefix}-A")],
            "legs": [bank("x", amount, reference=f"{prefix}-B")],
        },
        {"a": None},
        "The amount agrees but explicit reference evidence rules out the link.",
    )
    yield Scenario(
        "tolerated_difference",
        {
            "payments": [claim("a", amount, reference=prefix)],
            "legs": [bank("x", amount + 1, reference=prefix)],
            "policy": {"tolerance_minor": 1},
        },
        {"a": ["x"]},
        "One minor unit of difference is accepted only by an explicit policy.",
    )
    yield Scenario(
        "indistinguishable_decoy",
        {"payments": [claim("a", amount)], "legs": [bank("x", amount)]},
        {"a": None},
        "A coincident amount/date creates a unique optimum but a false business link.",
    )


def counts():
    return {
        "cases": 0,
        "payments": 0,
        "known_links": 0,
        "suggestions": 0,
        "correct_suggestions": 0,
        "false_suggestions": 0,
        "ambiguous_payments": 0,
        "unmatched_payments": 0,
        "incomplete_cases": 0,
    }


def metrics(value):
    result = dict(value)
    for label, numerator, denominator in [
        ("precision", "correct_suggestions", "suggestions"),
        ("recall_of_known_links", "correct_suggestions", "known_links"),
        ("coverage", "suggestions", "payments"),
        ("ambiguous_fraction", "ambiguous_payments", "payments"),
    ]:
        result[label] = (
            round(value[numerator] / value[denominator], 6) if value[denominator] else None
        )
    return result


def observe(aggregate, scenario, result):
    aggregate["cases"] += 1
    aggregate["payments"] += len(scenario.request["payments"])
    aggregate["known_links"] += sum(value is not None for value in scenario.truth.values())
    aggregate["suggestions"] += len(result["suggestions"])
    for suggestion in result["suggestions"]:
        expected = scenario.truth[suggestion["payment_id"]]
        correct = expected is not None and set(expected) == set(suggestion["leg_ids"])
        aggregate["correct_suggestions" if correct else "false_suggestions"] += 1
    aggregate["ambiguous_payments"] += sum(
        row["status"] == "ambiguous" for row in result["decisions"]
    )
    aggregate["unmatched_payments"] += sum(
        row["status"] == "unmatched" for row in result["decisions"]
    )
    aggregate["incomplete_cases"] += not result["complete"]


def timing(samples):
    ordered = sorted(samples)
    return {
        "samples": len(samples),
        "method": "nearest rank; sequential local engine calls",
        **{
            f"p{percentile}_ms": round(ordered[math.ceil(len(ordered) * percentile / 100) - 1], 3)
            for percentile in [50, 95, 99]
        },
        "raw_ms": [round(value, 3) for value in samples],
    }


def evaluate(trials=40, seed=20261030):
    if type(trials) is not int or not 1 <= trials <= 200:
        raise ValueError("trials must be1..200")
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("seed must be an unsigned32-bit integer")
    dataset = [scenario for offset in range(trials) for scenario in scenarios(seed + offset)]
    result = {
        "version": "settlement-forensics-evaluation-v1",
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "seed": seed,
        "trials_per_scenario": trials,
        "scenario_count": len(dataset),
        "scenario_sha256": digest(
            [{"name": row.name, "request": row.request, "truth": row.truth} for row in dataset]
        ),
        "policies": {},
        "methodology": [
            "Deterministic synthetic scenarios with independently retained allocation labels.",
            "No fitting/training; labels never enter candidate generation or optimization.",
            "Each policy is evaluated on the same cases; measures are descriptive counts.",
            "A false decoy is retained deliberately; a unique optimum is not business certainty.",
            "Scenario strata are designed, not an estimate of a production population.",
            "No confidence interval, production SLA or perfect matching claim is inferred.",
        ],
    }
    for policy_name, overrides in [
        ("default", {}),
        ("complete_reference", {"require_complete_reference": True}),
    ]:
        aggregate, by_scenario, samples = counts(), {}, []
        for scenario in dataset:
            request = {
                **scenario.request,
                "policy": {**scenario.request.get("policy", {}), **overrides},
            }
            start = time.perf_counter()
            report = analyze(request)
            samples.append((time.perf_counter() - start) * 1000)
            observe(aggregate, scenario, report)
            observe(by_scenario.setdefault(scenario.name, counts()), scenario, report)
        result["policies"][policy_name] = {
            **metrics(aggregate),
            "by_scenario": {key: metrics(value) for key, value in by_scenario.items()},
            "engine_timing": timing(samples),
        }
    return result
