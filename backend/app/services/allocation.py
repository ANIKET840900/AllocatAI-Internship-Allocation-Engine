import time

from ortools.sat.python import cp_model

from app.services.matching import eligibility, score


def allocate(candidates, internships, weights=None, timeout_seconds=30):
    started = time.perf_counter()
    model = cp_model.CpModel()
    variables, pair_data = {}, {}
    candidates = sorted(candidates, key=lambda row: row["candidate_id"])
    internships = sorted(internships, key=lambda row: row["internship_id"])
    for candidate in candidates:
        for internship in internships:
            result = eligibility(candidate, internship)
            if result["eligible"] and internship["available_seats"] > 0:
                value, components = score(candidate, internship, weights)
                key = (candidate["candidate_id"], internship["internship_id"])
                variables[key] = model.NewBoolVar(f"x_{key[0]}_{key[1]}")
                pair_data[key] = {"score": value, "components": components, "eligibility": result}
    for candidate in candidates:
        model.Add(sum(var for (candidate_id, _), var in variables.items() if candidate_id == candidate["candidate_id"]) <= 1)
    for internship in internships:
        model.Add(sum(var for (_, internship_id), var in variables.items() if internship_id == internship["internship_id"]) <= internship["available_seats"])
    model.Maximize(sum(int(data["score"] * 100) * variables[key] for key, data in pair_data.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, float(timeout_seconds))
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    status_name = solver.StatusName(status)
    allocations = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for key, variable in variables.items():
            if solver.Value(variable):
                data = pair_data[key]
                allocations.append({"candidate_id": key[0], "internship_id": key[1], **data})
    allocated_ids = {row["candidate_id"] for row in allocations}
    unmatched = [row["candidate_id"] for row in candidates if row["candidate_id"] not in allocated_ids]
    capacity_ok = all(
        sum(row["internship_id"] == internship["internship_id"] for row in allocations) <= internship["available_seats"]
        for internship in internships
    )
    return {
        
        "status": status_name,
        "objective_value": round(solver.ObjectiveValue() / 100, 4) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else 0,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 2),
        "allocations": allocations,
        "unmatched_candidates": unmatched,
        "pair_count": len(pair_data),
        "validation": {"unique_candidates": len(allocated_ids) == len(allocations), "capacity_ok": capacity_ok},
    }
