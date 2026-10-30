"""Generate auditable bounded candidate groups without converting currencies."""

import time
from dataclasses import dataclass
from itertools import combinations

from settlement_recon.forensics_models import ForensicsRequest

MAX_CANDIDATES = 10_000
MAX_COMBINATION_CHECKS = 150_000
MAX_COMPONENT_PAYMENTS = 10
MAX_COMPONENT_LEGS = 16
MAX_SECONDS = 2.0


class WorkExhausted(Exception):
    """An incomplete search must abstain; it must never masquerade as an optimum."""


@dataclass
class WorkBudget:
    deadline: float
    max_states: int
    states: int = 0
    checks: int = 0

    def check_time(self):
        if time.monotonic() >= self.deadline:
            raise WorkExhausted

    def combination(self):
        self.checks += 1
        if self.checks > MAX_COMBINATION_CHECKS:
            raise WorkExhausted
        if self.checks % 128 == 1:
            self.check_time()

    def state(self):
        if self.states >= self.max_states:
            raise WorkExhausted
        self.states += 1
        if self.states % 64 == 1:
            self.check_time()


@dataclass(frozen=True)
class Candidate:
    payment: int
    legs: tuple[int, ...]
    score: tuple[int, ...]
    difference: int
    settled: int
    reference_evidence: str
    maximum_lag: int | None
    complete_dates: bool


def reference(value):
    return (
        "".join(character.upper() for character in value if character.isalnum()) if value else None
    )


def generate(request: ForensicsRequest, budget: WorkBudget):
    """Return every eligible group within hard work limits, never a silent top-k."""
    result = {index: [] for index in range(len(request.payments))}
    count = 0
    policy = request.policy
    for index, payment in enumerate(request.payments):
        available = []
        wanted_reference = reference(payment.reference)
        if policy.require_complete_reference and not wanted_reference:
            continue
        for position, leg in enumerate(request.legs):
            if leg.currency != payment.currency:
                continue
            supplied_reference = reference(leg.reference)
            if policy.require_complete_reference and supplied_reference != wanted_reference:
                continue
            if policy.require_reference_agreement and wanted_reference and supplied_reference:
                if wanted_reference != supplied_reference:
                    continue
            if policy.require_date_evidence and (
                payment.expected_on is None or leg.settled_on is None
            ):
                continue
            if payment.expected_on and leg.settled_on:
                if abs((leg.settled_on - payment.expected_on).days) > policy.max_lag_days:
                    continue
            available.append(position)
        for size in range(1, policy.max_split + 1):
            for positions in combinations(available, size):
                budget.combination()
                selected = [request.legs[position] for position in positions]
                total = sum(leg.net_minor + leg.fee_minor for leg in selected)
                difference = payment.amount_minor - total
                if abs(difference) > policy.tolerance_minor:
                    continue
                refs = [reference(leg.reference) for leg in selected]
                exact = bool(wanted_reference and all(value == wanted_reference for value in refs))
                conflicts = bool(
                    wanted_reference and any(value and value != wanted_reference for value in refs)
                )
                evidence = "exact" if exact else ("conflict_allowed" if conflicts else "missing")
                lags = [
                    abs((leg.settled_on - payment.expected_on).days)
                    for leg in selected
                    if payment.expected_on is not None and leg.settled_on is not None
                ]
                complete_dates = len(lags) == len(selected)
                score = (1, int(exact), -abs(difference), int(complete_dates), -sum(lags), -size)
                result[index].append(
                    Candidate(
                        index,
                        positions,
                        score,
                        difference,
                        total,
                        evidence,
                        max(lags) if lags else None,
                        complete_dates,
                    )
                )
                count += 1
                if count > MAX_CANDIDATES:
                    raise WorkExhausted
        result[index].sort(key=lambda row: (tuple(-part for part in row.score), row.legs))
    budget.check_time()
    return result


def components(candidates):
    """Candidate overlap defines independent exact-optimization components."""
    reverse = {}
    for payment, choices in candidates.items():
        for choice in choices:
            for leg in choice.legs:
                reverse.setdefault(leg, set()).add(payment)
    remaining = set(candidates)
    result = []
    while remaining:
        queue = [min(remaining)]
        payments, legs = set(), set()
        while queue:
            payment = queue.pop()
            if payment in payments:
                continue
            payments.add(payment)
            remaining.discard(payment)
            for choice in candidates[payment]:
                for leg in choice.legs:
                    if leg not in legs:
                        legs.add(leg)
                        queue.extend(reverse[leg] - payments)
        result.append((tuple(sorted(payments)), tuple(sorted(legs))))
    return result
