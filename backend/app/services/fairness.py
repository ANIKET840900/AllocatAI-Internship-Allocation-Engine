from collections import defaultdict


def fairness_report(audit_rows, allocations, eligible_candidate_ids=None):
    selected = {row["candidate_id"] for row in allocations}
    groups = defaultdict(list)
    for row in audit_rows:
        groups[row["group_name"]].append(row["candidate_id"])
    rates = {group: (sum(candidate_id in selected for candidate_id in ids) / len(ids) if ids else 0.0) for group, ids in groups.items()}
    eligible = set(eligible_candidate_ids) if eligible_candidate_ids is not None else set()
    opportunity_rates = {
        group: sum(candidate_id in selected for candidate_id in ids if candidate_id in eligible)
        / max(sum(candidate_id in eligible for candidate_id in ids), 1)
        for group, ids in groups.items()
        if any(candidate_id in eligible for candidate_id in ids)
    }
    reference = max(rates, key=rates.get) if rates else None
    reference_rate = rates.get(reference, 0.0) if reference else 0.0
    return {
        "selection_rates": rates,
        "unmatched_rates": {group: 1 - rate for group, rate in rates.items()},
        "eligible_selection_rates": opportunity_rates,
        "equal_opportunity_difference": max(opportunity_rates.values()) - min(opportunity_rates.values()) if len(opportunity_rates) > 1 else None,
        "reference_group": reference,
        "demographic_parity_difference": max(rates.values()) - min(rates.values()) if rates else 0.0,
        "disparate_impact_ratio": min(rates.values()) / reference_rate if rates and reference_rate else 0.0,
        "allocated_count": len(selected),
        "limitations": "Audit metrics are descriptive signals; small groups and missing audit data limit interpretation and do not establish legal compliance.",
    }
