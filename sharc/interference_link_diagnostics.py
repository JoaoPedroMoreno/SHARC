"""Deterministic ranking helpers for per-link interference diagnostics.

This module is deliberately independent from handover selection and random
number generation.  Linear powers use mW, matching SHARC's conversion from
dBm via ``10 ** (0.1 * power_dbm)``.
"""

from __future__ import annotations

import math

import numpy as np


def select_diagnostic_links(
    records: list[dict],
    aggregate_linear_mw: float,
    top_n: int = 10,
) -> tuple[list[dict], dict]:
    """Rank links and retain top-N plus every handover-affected link."""
    if top_n < 1:
        raise ValueError("top_n must be at least 1")
    if not np.isfinite(aggregate_linear_mw) or aggregate_linear_mw <= 0.0:
        raise ValueError("aggregate_linear_mw must be positive and finite")

    powers = np.asarray(
        [record["i_link_linear_mw"] for record in records], dtype=float)
    if powers.size == 0:
        raise ValueError("at least one link record is required")
    if np.any(~np.isfinite(powers)) or np.any(powers < 0.0):
        raise ValueError("link powers must be finite and non-negative")

    order = np.argsort(-powers, kind="stable")
    ranks = np.empty(powers.size, dtype=int)
    ranks[order] = np.arange(1, powers.size + 1)
    retained = set(order[:min(top_n, powers.size)].tolist())
    retained.update(
        index for index, record in enumerate(records)
        if record.get("trigger_flag", False)
        or record.get("handover_flag", False)
        or record.get("unresolved_flag", False)
    )

    def top_fraction(count: int) -> float:
        return float(np.sum(powers[order[:min(count, powers.size)]]) /
                     aggregate_linear_mw)

    fractions = {
        "fraction_top1": top_fraction(1),
        "fraction_top3": top_fraction(3),
        "fraction_top5": top_fraction(5),
        "fraction_top10": top_fraction(10),
    }
    selected = []
    for index in sorted(retained, key=lambda item: ranks[item]):
        row = records[index].copy()
        row["rank_in_snapshot"] = int(ranks[index])
        row["fraction_of_iagg_linear"] = float(
            powers[index] / aggregate_linear_mw)
        row.update(fractions)
        selected.append(row)

    reconstructed = float(np.sum(powers))
    summary = {
        "active_links_evaluated": int(powers.size),
        "recorded_links": int(len(selected)),
        "i_agg_linear_mw": float(aggregate_linear_mw),
        "i_agg_dbm": float(10.0 * math.log10(aggregate_linear_mw)),
        "sum_i_link_linear_mw": reconstructed,
        "sum_error_linear_mw": reconstructed - aggregate_linear_mw,
        **fractions,
    }
    return selected, summary
