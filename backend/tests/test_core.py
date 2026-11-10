import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.allocation import allocate
from app.services.fairness import fairness_report
from app.services.matching import eligibility, score
from app.services.synthetic_data import generate_dataset


def test_synthetic_generation_is_reproducible():
    left = generate_dataset(4, 2, 7)
    right = generate_dataset(4, 2, 7)
    assert left == right


def test_ineligible_candidate_is_rejected():
    candidate = {"cgpa": 6, "education": "B.Sc", "experience_months": 0, "technical_skills": []}
    internship = {"minimum_cgpa": 8, "required_education": "B.Tech", "minimum_experience": 3, "required_skills": ["Python"]}
    assert not eligibility(candidate, internship)["eligible"]


def test_global_allocation_respects_candidate_and_capacity_constraints():
    candidates = [{"candidate_id": "C1", "cgpa": 9, "education": "B.Tech", "experience_months": 12, "technical_skills": ["Python"], "preferred_domains": ["AI"], "preferred_locations": ["Remote"], "preferred_duration": 3}]
    internship = {"internship_id": "I1", "domain": "AI", "location": "Remote", "duration": 3, "minimum_cgpa": 5, "required_education": "Any", "minimum_experience": 0, "required_skills": ["Python"], "preferred_skills": [], "available_seats": 1}
    result = allocate(candidates, [internship])
    assert len(result["allocations"]) == 1
    assert result["allocations"][0]["candidate_id"] == "C1"
    assert result["validation"] == {"unique_candidates": True, "capacity_ok": True}


def test_zero_seat_and_ineligible_pairs_remain_unmatched():
    candidate = {
        "candidate_id": "C1", "cgpa": 5, "education": "B.Sc", "experience_months": 0,
        "technical_skills": [], "preferred_domains": [], "preferred_locations": [], "preferred_duration": 3,
    }
    no_seats = {
        "internship_id": "I0", "domain": "AI", "location": "Remote", "duration": 3,
        "minimum_cgpa": 0, "required_education": "Any", "minimum_experience": 0,
        "required_skills": [], "preferred_skills": [], "available_seats": 0,
    }
    result = allocate([candidate], [no_seats])
    assert result["allocations"] == []
    assert result["unmatched_candidates"] == ["C1"]
    assert result["validation"] == {"unique_candidates": True, "capacity_ok": True}

    positive_seats = {**no_seats, "internship_id": "I1", "available_seats": 1, "minimum_cgpa": 9}
    result = allocate([candidate], [positive_seats])
    assert result["allocations"] == []
    assert result["pair_count"] == 0


def test_allocation_is_stable_when_input_order_changes():
    candidates, internships, _ = generate_dataset(20, 6, 12)
    forward = allocate(candidates, internships)
    reverse = allocate(list(reversed(candidates)), list(reversed(internships)))
    forward_pairs = [(row["candidate_id"], row["internship_id"], row["score"]) for row in forward["allocations"]]
    reverse_pairs = [(row["candidate_id"], row["internship_id"], row["score"]) for row in reverse["allocations"]]
    assert forward_pairs == reverse_pairs


def test_weighted_score_is_bounded_and_explainable():
    candidate = {
        "candidate_id": "C1", "cgpa": 8, "education": "B.Tech", "experience_months": 12,
        "technical_skills": ["Python"], "preferred_domains": ["AI"], "preferred_locations": ["Remote"], "preferred_duration": 3,
    }
    internship = {
        "internship_id": "I1", "domain": "AI", "location": "Remote", "duration": 3,
        "minimum_cgpa": 7, "required_education": "B.Tech", "minimum_experience": 0,
        "required_skills": ["Python"], "preferred_skills": [], "available_seats": 1,
    }
    value, components = score(candidate, internship)
    assert 0 <= value <= 100
    assert set(components) == {"skill", "education", "preference", "location", "experience", "other"}
    assert all(0 <= component <= 100 for component in components.values())


def test_fairness_report_uses_audit_groups():
    audit = [{"candidate_id": "C1", "group_name": "A"}, {"candidate_id": "C2", "group_name": "B"}]
    report = fairness_report(audit, [{"candidate_id": "C1"}])
    assert report["selection_rates"] == {"A": 1.0, "B": 0.0}
    assert report["disparate_impact_ratio"] == 0.0
    assert report["equal_opportunity_difference"] is None


def test_fairness_report_calculates_eligible_conditioned_rates_and_unmatched():
    audit = [
        {"candidate_id": "C1", "group_name": "A"},
        {"candidate_id": "C2", "group_name": "A"},
        {"candidate_id": "C3", "group_name": "B"},
    ]
    report = fairness_report(audit, [{"candidate_id": "C1"}, {"candidate_id": "C3"}], {"C1", "C2", "C3"})
    assert report["eligible_selection_rates"] == {"A": 0.5, "B": 1.0}
    assert report["equal_opportunity_difference"] == 0.5
    assert report["unmatched_rates"] == {"A": 0.5, "B": 0.0}
