"""Exact bounded set packing, retaining consensus over every optimal allocation."""

from functools import cache

from settlement_recon.forensics_candidates import WorkBudget

ZERO = (0, 0, 0, 0, 0, 0)
COUNT_CAP = 1_000_000


def add(first, second):
    return tuple(a + b for a, b in zip(first, second, strict=True))


def solve(payment_indices, leg_indices, candidates, budget: WorkBudget):
    """DP returns score/count; optimal-transition traversal returns per-payment choices.

    Identifier order only makes the traversal reproducible. It cannot resolve a tie:
    every optimal transition contributes to the alternatives reported to the analyst.
    """
    positions = {leg: position for position, leg in enumerate(leg_indices)}
    options = []
    for payment in payment_indices:
        choices = [(None, 0, ZERO)]
        for candidate in candidates[payment]:
            mask = sum(1 << positions[leg] for leg in candidate.legs)
            choices.append((candidate, mask, candidate.score))
        options.append(choices)

    @cache
    def best(index, used):
        budget.state()
        if index == len(payment_indices):
            return ZERO, 1, False
        optimum = None
        count = 0
        capped = False
        for _candidate, mask, score in options[index]:
            if used & mask:
                continue
            tail, multiplicity, child_capped = best(index + 1, used | mask)
            value = add(score, tail)
            if optimum is None or value > optimum:
                optimum, count, capped = value, multiplicity, child_capped
            elif value == optimum:
                combined = count + multiplicity
                capped = capped or child_capped or combined > COUNT_CAP
                count = min(combined, COUNT_CAP)
        return optimum, count, capped

    objective, count, capped = best(0, 0)
    alternatives = {payment: set() for payment in payment_indices}
    pending = [(0, 0)]
    visited = set()
    while pending:
        index, used = pending.pop()
        if (index, used) in visited or index == len(payment_indices):
            continue
        visited.add((index, used))
        budget.check_time()
        optimum = best(index, used)[0]
        for candidate, mask, score in options[index]:
            if used & mask:
                continue
            if add(score, best(index + 1, used | mask)[0]) == optimum:
                alternatives[payment_indices[index]].add(candidate.legs if candidate else None)
                pending.append((index + 1, used | mask))
    return objective, count, capped, alternatives
