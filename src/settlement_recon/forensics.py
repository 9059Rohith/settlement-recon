"""Advisory allocation investigations: explicit evidence, optimality and abstention."""

import hashlib
import json
import time

from settlement_recon.forensics_candidates import (
    MAX_COMPONENT_LEGS,
    MAX_COMPONENT_PAYMENTS,
    MAX_SECONDS,
    WorkBudget,
    WorkExhausted,
    components,
    generate,
)
from settlement_recon.forensics_models import ForensicsReport, ForensicsRequest
from settlement_recon.forensics_solver import solve

OBJECTIVE = [
    "matched_payment_count",
    "complete_reference_agreement",
    "negative_absolute_difference",
    "complete_date_evidence",
    "negative_total_lag_days",
    "negative_leg_count",
]
LIMITATIONS = [
    "Advisory only: no bank or ledger records are created, linked or modified.",
    "A unique submitted-data optimum is not a probability or proof of a business match.",
    "Candidate eligibility and lexicographic preferences are explicit analyst policy assumptions.",
    "No FX conversion, negative adjustments, chargebacks or fractional allocation of a bank leg.",
    "At most 10 payments/16 legs per connected component; bounded work can require abstention.",
]


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


def normalize(value):
    request = (
        value if isinstance(value, ForensicsRequest) else ForensicsRequest.model_validate(value)
    )
    return request.model_copy(
        update={
            "payments": sorted(request.payments, key=lambda row: row.payment_id),
            "legs": sorted(request.legs, key=lambda row: row.leg_id),
        }
    )


def failed_decision(payment, status, candidate_count=0):
    return {
        "payment_id": payment.payment_id,
        "status": status,
        "candidates": candidate_count,
        "alternatives": [],
        "alternatives_truncated": False,
    }


def certificate(request, payments, legs, status, objective=None, count=None, capped=False):
    return {
        "payment_ids": [request.payments[index].payment_id for index in payments],
        "leg_ids": [request.legs[index].leg_id for index in legs],
        "status": status,
        "objective": list(objective) if objective is not None else None,
        "optimal_allocations": count,
        "allocation_count_capped": capped,
    }


def analyze(value: ForensicsRequest | dict) -> dict:
    start = time.monotonic()
    request = normalize(value)
    budget = WorkBudget(start + MAX_SECONDS, request.policy.max_states)
    result = {
        "version": "settlement-forensics-v1",
        "advisory_only": True,
        "complete": True,
        "request_sha256": digest(request.model_dump(mode="json")),
        "policy_sha256": digest(request.policy.model_dump(mode="json")),
        "objective_order": OBJECTIVE,
        "candidates_considered": 0,
        "combination_checks": 0,
        "search_states": 0,
        "elapsed_ms": 0.0,
        "components": [],
        "decisions": [],
        "suggestions": [],
        "limitations": LIMITATIONS,
    }
    try:
        candidates = generate(request, budget)
    except WorkExhausted:
        result["complete"] = False
        result["components"].append(
            certificate(
                request, range(len(request.payments)), range(len(request.legs)), "budget_exceeded"
            )
        )
        result["decisions"] = [failed_decision(row, "budget_exceeded") for row in request.payments]
        return finish(result, budget, start)
    result["candidates_considered"] = sum(len(rows) for rows in candidates.values())
    for payments, legs in components(candidates):
        status = "complete"
        if len(payments) > MAX_COMPONENT_PAYMENTS or len(legs) > MAX_COMPONENT_LEGS:
            status = "capacity_exceeded"
        if status == "complete":
            try:
                objective, count, capped, choices = solve(payments, legs, candidates, budget)
            except WorkExhausted:
                status = "budget_exceeded"
        if status != "complete":
            result["complete"] = False
            result["components"].append(certificate(request, payments, legs, status))
            result["decisions"].extend(
                failed_decision(request.payments[index], status, len(candidates[index]))
                for index in payments
            )
            continue
        result["components"].append(
            certificate(request, payments, legs, status, objective, count, capped)
        )
        for index in payments:
            possible = choices[index]
            status = (
                "ambiguous"
                if len(possible) > 1
                else ("unmatched" if possible == {None} else "unique")
            )
            ordered = sorted(possible, key=lambda item: (item is not None, item or ()))
            result["decisions"].append(
                {
                    "payment_id": request.payments[index].payment_id,
                    "status": status,
                    "candidates": len(candidates[index]),
                    "alternatives": [
                        [request.legs[leg].leg_id for leg in option] if option is not None else None
                        for option in ordered[:5]
                    ],
                    "alternatives_truncated": len(ordered) > 5,
                }
            )
            if status == "unique":
                selected = next(iter(possible))
                chosen = next(row for row in candidates[index] if row.legs == selected)
                payment = request.payments[index]
                result["suggestions"].append(
                    {
                        "payment_id": payment.payment_id,
                        "currency": payment.currency,
                        "leg_ids": [request.legs[position].leg_id for position in chosen.legs],
                        "expected_minor": payment.amount_minor,
                        "settled_minor": chosen.settled,
                        "difference_minor": chosen.difference,
                        "reference_evidence": chosen.reference_evidence,
                        "max_lag_days": chosen.maximum_lag,
                        "date_evidence_complete": chosen.complete_dates,
                    }
                )
    result["decisions"].sort(key=lambda row: row["payment_id"])
    result["suggestions"].sort(key=lambda row: row["payment_id"])
    return finish(result, budget, start)


def finish(result, budget, start):
    result["combination_checks"] = budget.checks
    result["search_states"] = budget.states
    result["elapsed_ms"] = round((time.monotonic() - start) * 1000, 3)
    return ForensicsReport.model_validate(result).model_dump(mode="json")
