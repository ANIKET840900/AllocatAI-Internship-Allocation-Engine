def _overlap(left, right):
    left_set, right_set = {str(x).lower() for x in left}, {str(x).lower() for x in right}
    return len(left_set & right_set) / max(len(right_set), 1)


def eligibility(candidate, internship):
    reasons = []
    review = []
    if candidate["cgpa"] < internship["minimum_cgpa"]:
        reasons.append("CGPA below minimum")
    required_education = internship["required_education"]
    if required_education != "Any" and candidate["education"] != required_education:
        reasons.append("Education requirement not met")
    if candidate.get("experience_months") is None:
        review.append("Experience is missing")
    elif candidate["experience_months"] < internship["minimum_experience"]:
        reasons.append("Experience below minimum")
    candidate_skills = candidate.get("technical_skills") or []
    required_skills = internship.get("required_skills") or []
    missing = set(map(str.lower, required_skills)) - set(map(str.lower, candidate_skills))
    if missing:
        reasons.append(f"Missing required skills: {', '.join(sorted(missing))}")
    return {"eligible": not reasons and not review, "reasons": reasons, "review": review}


def score(candidate, internship, weights=None):
    weights = weights or {"skill": .35, "education": .20, "preference": .15, "location": .15, "experience": .10, "other": .05}
    skill = min(1.0, (_overlap(candidate.get("technical_skills", []), internship.get("required_skills", [])) + .5 * _overlap(candidate.get("technical_skills", []), internship.get("preferred_skills", []))))
    education = 1.0 if internship["required_education"] == "Any" or candidate["education"] == internship["required_education"] else 0.0
    preference = float(internship["domain"] in candidate["preferred_domains"])
    location = float(internship["location"] in candidate["preferred_locations"])
    experience = min(candidate.get("experience_months", 0) / max(internship.get("minimum_experience", 0), 12), 1.0)
    other = float(abs(candidate.get("preferred_duration", 0) - internship.get("duration", 0)) <= 1)
    components = {"skill": skill * 100, "education": education * 100, "preference": preference * 100, "location": location * 100, "experience": experience * 100, "other": other * 100}
    total = sum(components[key] * weights[key] for key in components)
    return round(total, 4), components
