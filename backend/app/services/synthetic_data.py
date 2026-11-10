import random

EDUCATION = ["B.Tech", "B.Sc", "M.Tech", "MCA"]
DOMAINS = ["AI", "Web", "Data", "Cybersecurity", "Cloud", "Product"]
LOCATIONS = ["Bengaluru", "Pune", "Hyderabad", "Delhi", "Remote"]
SKILLS = ["Python", "JavaScript", "SQL", "React", "FastAPI", "ML", "Docker", "AWS", "Testing"]


def generate_dataset(candidate_count: int, internship_count: int, seed: int = 42):
    # Seeded randomness here creates reproducible synthetic data, not security tokens.
    rng = random.Random(seed)  # nosec B311
    candidates = []
    audit = []
    for index in range(candidate_count):
        skills = rng.sample(SKILLS, k=rng.randint(2, 5))
        candidate_id = f"C{index + 1:05d}"
        candidates.append({
            "candidate_id": candidate_id, "name": f"Candidate {index + 1}",
            "education": rng.choice(EDUCATION), "specialization": rng.choice(DOMAINS),
            "cgpa": round(rng.uniform(6.0, 10.0), 2), "technical_skills": skills,
            "soft_skills": rng.sample(["Communication", "Leadership", "Teamwork", "Adaptability"], 2),
            "experience_months": rng.randint(0, 24), "preferred_domains": rng.sample(DOMAINS, 2),
            "preferred_locations": rng.sample(LOCATIONS, 2), "preferred_stipend": rng.choice([10000, 15000, 20000]),
            "preferred_duration": rng.choice([2, 3, 6]), "preference_rank": [],
        })
        audit.append({"candidate_id": candidate_id, "group_name": rng.choice(["Group A", "Group B", "Group C"])})
    internships = []
    for index in range(internship_count):
        required = rng.sample(SKILLS, k=rng.randint(1, 3))
        internships.append({
            "internship_id": f"I{index + 1:04d}", "company_name": f"Company {index % 20 + 1}",
            "role": f"{rng.choice(DOMAINS)} Intern", "domain": rng.choice(DOMAINS),
            "required_skills": required, "preferred_skills": rng.sample(SKILLS, 2),
            "minimum_cgpa": rng.choice([6.0, 6.5, 7.0, 7.5]), "required_education": rng.choice(EDUCATION + ["Any"]),
            "minimum_experience": rng.choice([0, 3, 6, 12]), "location": rng.choice(LOCATIONS),
            "stipend": rng.choice([10000, 15000, 20000]), "duration": rng.choice([2, 3, 6]),
            "available_seats": rng.randint(1, 8), "mandatory_requirements": [],
        })
    return candidates, internships, audit
