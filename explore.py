import json

def load_candidates(path):
    candidates = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    return candidates

def print_candidate(c):
    p = c["profile"]
    sig = c["redrob_signals"]

    print("=" * 60)
    print(f"ID:           {c['candidate_id']}")
    print(f"Title:        {p['current_title']}")
    print(f"Company:      {p['current_company']} ({p['current_company_size']})")
    print(f"Industry:     {p['current_industry']}")
    print(f"Location:     {p['location']}, {p['country']}")
    print(f"Experience:   {p['years_of_experience']} years")
    print(f"Headline:     {p['headline']}")
    print()
    print("--- CAREER HISTORY ---")
    for job in c["career_history"]:
        print(f"  {job['title']} @ {job['company']} ({job['duration_months']} months)")
    print()
    print("--- SKILLS ---")
    for s in c["skills"][:6]:
        print(f"  {s['name']} | {s['proficiency']} | {s.get('duration_months', 0)}mo | {s['endorsements']} endorsements")
    print()
    print("--- REDROB SIGNALS ---")
    print(f"  Open to work:      {sig['open_to_work_flag']}")
    print(f"  Last active:       {sig['last_active_date']}")
    print(f"  Notice period:     {sig['notice_period_days']} days")
    print(f"  Response rate:     {sig['recruiter_response_rate']}")
    print(f"  Interview rate:    {sig['interview_completion_rate']}")
    print(f"  GitHub score:      {sig['github_activity_score']}")
    print(f"  Willing to relocate: {sig['willing_to_relocate']}")
    print(f"  Salary (LPA):      {sig['expected_salary_range_inr_lpa']}")
    print("=" * 60)

if __name__ == "__main__":
    print("Loading candidates...")
    candidates = load_candidates("candidates.jsonl")
    print(f"Loaded {len(candidates):,} candidates\n")

    # Print first 3 candidates
    for c in candidates[:3]:
        print_candidate(c)