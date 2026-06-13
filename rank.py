# rank.py
import json
import csv
import math
import re
import argparse
from datetime import date, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# JD CONSTANTS — derived from careful reading of job_description.docx
# ---------------------------------------------------------------------------

# Core skills the JD explicitly requires
REQUIRED_SKILLS = [
    "embeddings", "vector database", "semantic search", "retrieval", "ranking",
    "sentence-transformers", "faiss", "pinecone", "weaviate", "qdrant", "milvus",
    "elasticsearch", "opensearch", "hybrid search", "dense retrieval",
    "python", "nlp", "natural language processing", "information retrieval",
    "llm", "large language model", "fine-tuning", "lora", "qlora", "peft",
    "rag", "retrieval augmented generation", "recommendation system",
    "machine learning", "deep learning", "transformer", "bert",
    "ndcg", "mrr", "a/b testing", "pytorch", "tensorflow", "huggingface",
    "hugging face", "mlops", "model serving", "pgvector", "reranking",
    "sparse retrieval", "bm25", "colbert", "cross-encoder"
]

# Title keywords that signal the right engineering background
AI_TITLE_KEYWORDS = [
    "ai engineer", "ml engineer", "machine learning engineer", "applied scientist",
    "nlp engineer", "search engineer", "ranking engineer", "data scientist",
    "applied ml", "recommendation", "retrieval", "research scientist",
    "senior engineer", "staff engineer", "principal engineer"
]

# Firms the JD explicitly disqualifies (consulting-only background)
CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mphasis", "hexaware", "ltimindtree", "mindtree",
    "birlasoft", "persistent systems", "coforge", "niit technologies",
    "ibm global", "dxc technology"
}

# Locations the JD prefers — Pune/Noida first, rest acceptable
TARGET_LOCATIONS = {
    "pune", "noida", "mumbai", "hyderabad", "delhi", "gurgaon",
    "gurugram", "bangalore", "bengaluru", "ncr", "indore", "ahmedabad"
}

# Proficiency → numeric weight
PROFICIENCY_WEIGHT = {
    "beginner": 0.25,
    "intermediate": 0.55,
    "advanced": 0.80,
    "expert": 1.0
}

# Production ML keywords — presence in job descriptions signals real deployment
PRODUCTION_ML_KEYWORDS = [
    "deployed", "production", "serving", "inference", "pipeline",
    "embedding", "retrieval", "ranking", "search", "recommendation",
    "vector", "index", "latency", "throughput", "scale", "real-time",
    "a/b test", "evaluation", "ndcg", "mrr", "fine-tun", "rag",
    "rerank", "recall", "precision", "benchmark", "experiment"
]

# ---------------------------------------------------------------------------
# DATA LOADER
# ---------------------------------------------------------------------------

def load_candidates(path: str) -> list:
    candidates = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))
    print(f"Loaded {len(candidates):,} candidates")
    return candidates

# ---------------------------------------------------------------------------
# HONEYPOT DETECTION
# ---------------------------------------------------------------------------

def is_honeypot(candidate: dict) -> bool:
    profile   = candidate["profile"]
    career    = candidate["career_history"]
    skills    = candidate["skills"]
    yoe       = profile["years_of_experience"]

    # Check 1: A single job lasted longer than the candidate's entire career
    # This is the core honeypot signal — "8 years at a 3-year-old company"
    total_career_months = sum(j["duration_months"] for j in career)
    for job in career:
        if job["duration_months"] > total_career_months + 6:
            return True

    # Check 2: Expert skills with literally zero months of usage
    expert_zero = sum(
        1 for s in skills
        if s["proficiency"] == "expert" and s.get("duration_months", 1) == 0
    )
    if expert_zero >= 4:
        return True

    # Check 3: YOE is tiny but claims enormous career months
    # e.g., profile says 1.0 years but career_history sums to 8 years
    if total_career_months > (yoe * 12) + 24:
        return True

    # Check 4: Technology anachronism — only flag massive overages (2x+ impossible)
    TECH_RELEASE_MONTHS = {
        "rag": 73,
        "retrieval augmented generation": 73,
        "chatgpt": 31,
        "gpt-4": 26,
        "llama": 28,
        "langchain": 30,
        "llamaindex": 28,
        "pinecone": 43,
        "weaviate": 55,
        "qdrant": 43,
        "chromadb": 24,
    }

    for skill in skills:
        name  = skill["name"].lower()
        usage = skill.get("duration_months", 0)
        for tech, max_months in TECH_RELEASE_MONTHS.items():
            if tech in name and usage > max_months * 2.5:
                return True

    return False

# Component weights — must sum to 1.0
WEIGHT_SEMANTIC   = 0.20
WEIGHT_CAREER     = 0.28
WEIGHT_SKILLS     = 0.17
WEIGHT_SIGNALS    = 0.30
WEIGHT_EDUCATION  = 0.05

TODAY = date.today()

# ---------------------------------------------------------------------------
# COMPONENT 1: CAREER FIT
# ---------------------------------------------------------------------------

def score_career(candidate: dict) -> tuple:
    profile = candidate["profile"]
    career  = candidate["career_history"]
    notes   = []
    score   = 0.0

    yoe = profile["years_of_experience"]

    # --- Years of experience ---
    if 5 <= yoe <= 9:
        score += 0.25
        notes.append(f"{yoe:.1f} yrs exp (ideal band 5-9)")
    elif 4 <= yoe < 5 or 9 < yoe <= 12:
        score += 0.10
        notes.append(f"{yoe:.1f} yrs exp (near band)")
    elif yoe > 12:
        score += 0.08
        notes.append(f"{yoe:.1f} yrs exp (over-senior)")
    else:
        score += 0.03
        notes.append(f"{yoe:.1f} yrs exp (under-qualified)")

    # --- Consulting-only background check ---
    all_companies = [j["company"].lower() for j in career]
    consulting_jobs = sum(
        1 for c in all_companies
        if any(firm in c for firm in CONSULTING_FIRMS)
    )
    is_consulting_only = (consulting_jobs == len(career)) and len(career) > 0

    if is_consulting_only:
        score *= 0.25
        notes.append("consulting-only career (heavily penalized)")
        return round(min(score, 1.0), 4), notes

    # --- Title relevance ---
    current_title = profile.get("current_title", "").lower()
    title_score   = 0.0

    for kw in AI_TITLE_KEYWORDS:
        if kw in current_title:
            title_score = 0.25
            notes.append(f"strong title match: {profile['current_title']}")
            break

    # Check past titles too — career progression matters
    if title_score == 0:
        for job in career:
            for kw in AI_TITLE_KEYWORDS:
                if kw in job["title"].lower():
                    title_score = 0.12
                    notes.append(f"prior AI/ML title: {job['title']}")
                    break
            if title_score > 0:
                break

    score += title_score

    # --- Production ML signals in job descriptions ---
    prod_hits = 0
    for job in career:
        desc = job.get("description", "").lower()
        for kw in PRODUCTION_ML_KEYWORDS:
            if kw in desc:
                prod_hits += 1

    prod_score = min(prod_hits / 12.0, 1.0) * 0.30
    score += prod_score

    if prod_hits >= 8:
        notes.append(f"strong production ML signals ({prod_hits} hits)")
    elif prod_hits >= 3:
        notes.append(f"some production ML signals ({prod_hits} hits)")
    else:
        notes.append("weak production ML signals")

    # --- Penalize AI title with zero production signals ---
    # This catches researchers and tutorial-builders
    if title_score >= 0.25 and prod_hits == 0:
        score *= 0.5
        notes.append("AI title but no production signals (research penalty)")

    # --- Company size — product companies tend to be mid-size ---
    size = profile.get("current_company_size", "")
    if size in ["51-200", "201-500", "501-1000"]:
        score += 0.08
        notes.append("product-company size signal")
    elif size in ["1001-5000"]:
        score += 0.04

    # --- Industry signal ---
    industry = profile.get("current_industry", "").lower()
    good_industries = [
        "technology", "software", "saas", "ai", "fintech",
        "edtech", "healthtech", "e-commerce", "ml", "data"
    ]
    if any(ind in industry for ind in good_industries):
        score += 0.06
        notes.append(f"relevant industry: {profile['current_industry']}")

    return round(min(score, 1.0), 4), notes

# ---------------------------------------------------------------------------
# COMPONENT 2: SKILLS MATCH
# ---------------------------------------------------------------------------

def score_skills(candidate: dict) -> tuple:
    skills      = candidate["skills"]
    sig         = candidate["redrob_signals"]
    profile     = candidate["profile"]
    career      = candidate["career_history"]
    notes       = []

    if not skills:
        return 0.0, ["no skills listed"]

    assessment_scores = sig.get("skill_assessment_scores", {})
    matched           = []
    total_weight      = 0.0

    for skill in skills:
        name        = skill["name"].lower()
        proficiency = skill.get("proficiency", "beginner")
        endorsements = skill.get("endorsements", 0)
        duration    = skill.get("duration_months", 0)

        # Check if this skill matches any required skill
        is_match = any(req in name or name in req for req in REQUIRED_SKILLS)
        if not is_match:
            continue

        # Base score from proficiency
        base = PROFICIENCY_WEIGHT.get(proficiency, 0.25)

        # Endorsement multiplier — log scale so 100 endorsements
        # isn't 10x better than 10, just meaningfully better
        endorse_mult = 1.0 + min(math.log1p(endorsements) / 8.0, 0.35)

        # Duration multiplier — caps at 1.4x for 5+ years of usage
        duration_mult = 1.0 + min(duration / 60.0, 0.40)

        # Platform assessment boost — if they scored well on Redrob's
        # own skill test, that's stronger signal than self-reported proficiency
        assess_boost = 0.0
        for assess_key, assess_val in assessment_scores.items():
            if assess_key.lower() in name or name in assess_key.lower():
                assess_boost = (assess_val / 100.0) * 0.15
                break

        weight = (base * endorse_mult * duration_mult) + assess_boost
        total_weight += weight
        matched.append(skill["name"])

    if matched:
        notes.append(f"{len(matched)} relevant skills: {', '.join(matched[:4])}")

    # Normalize — 10 strong matched skills = full score
    score = min(total_weight / 10.0, 1.0)

    # --- Keyword stuffer detection ---
    # Many AI skills but career and title don't support them
    current_title   = profile.get("current_title", "").lower()
    title_is_non_ai = not any(kw in current_title for kw in AI_TITLE_KEYWORDS)

    career_has_ml = any(
        any(kw in job.get("description", "").lower()
            for kw in ["model", "embedding", "ml", "algorithm", "training",
                       "inference", "retrieval", "ranking", "vector"])
        for job in career
    )

    if len(matched) >= 6 and title_is_non_ai and not career_has_ml:
        score *= 0.35
        notes.append("keyword stuffer — skills don't match career history")

    return round(min(score, 1.0), 4), notes

# ---------------------------------------------------------------------------
# COMPONENT 3: BEHAVIORAL SIGNALS
# ---------------------------------------------------------------------------

def score_signals(candidate: dict) -> tuple:
    sig     = candidate["redrob_signals"]
    profile = candidate["profile"]
    notes   = []
    score   = 0.0

    # --- Open to work ---
    if sig["open_to_work_flag"]:
        score += 0.12
        notes.append("open to work")

    # --- Recency — last active date ---
    try:
        last_active  = datetime.strptime(sig["last_active_date"], "%Y-%m-%d").date()
        days_inactive = (TODAY - last_active).days

        if days_inactive <= 7:
            score += 0.20
            notes.append("active this week")
        elif days_inactive <= 30:
            score += 0.15
            notes.append(f"active {days_inactive}d ago")
        elif days_inactive <= 90:
            score += 0.08
            notes.append(f"active {days_inactive}d ago")
        elif days_inactive <= 180:
            score += 0.02
            notes.append(f"inactive {days_inactive}d")
        else:
            score -= 0.10
            notes.append(f"inactive {days_inactive}d — likely unavailable")
    except (ValueError, KeyError):
        pass

    # --- Notice period ---
    # JD wants sub-30 days, can buy out up to 30 days
    notice = sig.get("notice_period_days", 90)
    if notice == 0:
        score += 0.15
        notes.append("immediately available")
    elif notice <= 30:
        score += 0.12
        notes.append(f"{notice}d notice (ideal)")
    elif notice <= 60:
        score += 0.06
        notes.append(f"{notice}d notice (acceptable)")
    elif notice <= 90:
        score += 0.02
        notes.append(f"{notice}d notice (long)")
    else:
        score += 0.0
        notes.append(f"{notice}d notice (very long)")

    # --- Recruiter response rate ---
    response_rate = sig.get("recruiter_response_rate", 0)
    score += response_rate * 0.15
    if response_rate >= 0.70:
        notes.append(f"high response rate ({response_rate:.0%})")
    elif response_rate <= 0.15:
        notes.append(f"low response rate ({response_rate:.0%})")

    # --- Interview completion rate ---
    interview_rate = sig.get("interview_completion_rate", 0)
    score += interview_rate * 0.08

    # --- GitHub activity ---
    # For a Senior AI Engineer role this is a meaningful signal
    github = sig.get("github_activity_score", -1)
    if github >= 0:
        score += (github / 100.0) * 0.12
        if github >= 60:
            notes.append(f"strong GitHub activity ({github:.0f}/100)")

    # --- Profile completeness ---
    completeness = sig.get("profile_completeness_score", 0)
    score += (completeness / 100.0) * 0.05

    # --- Verification signals ---
    verified = sum([
        sig.get("verified_email", False),
        sig.get("verified_phone", False),
        sig.get("linkedin_connected", False)
    ])
    score += verified * 0.02

    # --- Location fit ---
    location          = profile.get("location", "").lower()
    country           = profile.get("country", "").lower()
    willing_to_relocate = sig.get("willing_to_relocate", False)

    if country == "india" and any(loc in location for loc in TARGET_LOCATIONS):
        score += 0.12
        notes.append(f"target location: {profile['location']}")
    elif country == "india" and willing_to_relocate:
        score += 0.06
        notes.append("India-based, willing to relocate")
    elif country == "india":
        score += 0.03
        notes.append("India-based")
    elif country != "india" and willing_to_relocate:
        score += 0.0
        notes.append("outside India, willing to relocate (no visa sponsorship)")
    else:
        score -= 0.12
        notes.append("outside India, not willing to relocate")

    # --- Salary fit scoring ---
    # Series A Senior AI Engineer budget: roughly 25-55 LPA
    BUDGET_MIN = 25
    BUDGET_MAX = 55
    salary  = sig.get("expected_salary_range_inr_lpa", {})
    sal_min = salary.get("min", 0)
    sal_max = salary.get("max", 0)

    if sal_min > 0 and sal_max > 0:
        # Check overlap between candidate range and budget range
        overlap_min = max(sal_min, BUDGET_MIN)
        overlap_max = min(sal_max, BUDGET_MAX)

        if overlap_max >= overlap_min:
            # There is overlap — score based on how well it fits
            overlap_size   = overlap_max - overlap_min
            candidate_range = sal_max - sal_min
            fit_ratio = overlap_size / max(candidate_range, 1)
            score += min(fit_ratio * 0.08, 0.08)
            if fit_ratio >= 0.5:
                notes.append(f"salary range fits budget ({sal_min}-{sal_max}L)")
        else:
            # No overlap
            if sal_min > BUDGET_MAX:
                score -= 0.08
                notes.append(f"salary above budget ({sal_min}L min vs {BUDGET_MAX}L max)")
            elif sal_max < BUDGET_MIN:
                score -= 0.03
                notes.append(f"salary suspiciously low ({sal_max}L max)")

    return round(min(max(score, 0.0), 1.0), 4), notes

# ---------------------------------------------------------------------------
# COMPONENT 5: EDUCATION TIER
# ---------------------------------------------------------------------------

def score_education(candidate: dict) -> tuple:
    education = candidate["education"]
    notes     = []

    if not education:
        return 0.0, []

    # Take the best tier across all education entries
    tier_scores = {
        "tier_1": 1.0,
        "tier_2": 0.65,
        "tier_3": 0.35,
        "tier_4": 0.15
    }

    best_score = 0.0
    best_tier  = None

    for edu in education:
        tier = edu.get("institution_tier", "")
        if tier in tier_scores:
            if tier_scores[tier] > best_score:
                best_score = tier_scores[tier]
                best_tier  = tier

    if best_tier:
        notes.append(f"education: {best_tier} institution")

    return round(best_score, 4), notes

# ---------------------------------------------------------------------------
# COMPONENT 4: SEMANTIC SIMILARITY
# ---------------------------------------------------------------------------

# Key terms from the JD — what the role is actually about
JD_TERMS = set("""
senior ai engineer founding team series retrieval ranking search embeddings
vector database semantic hybrid dense sparse python production deployment
recommendation nlp natural language processing information retrieval
fine tuning evaluation ndcg mrr pipeline inference scale latency
product company startup ship iterate candidate job matching talent
pytorch tensorflow huggingface sentence transformers faiss pinecone
weaviate qdrant elasticsearch opensearch reranking cross encoder
""".lower().split())


def build_candidate_text(candidate: dict) -> str:
    """Combine all text fields into one searchable blob."""
    p     = candidate["profile"]
    parts = [
        p.get("headline", ""),
        p.get("summary", ""),
        p.get("current_title", ""),
        p.get("current_industry", ""),
    ]
    for job in candidate["career_history"]:
        parts.append(job.get("title", ""))
        parts.append(job.get("description", ""))
        parts.append(job.get("industry", ""))
    for s in candidate["skills"]:
        parts.append(s["name"])
    for edu in candidate["education"]:
        parts.append(edu.get("field_of_study", ""))

    return " ".join(parts).lower()

# ---------------------------------------------------------------------------
# EMBEDDING UPGRADE (auto-detected)
# ---------------------------------------------------------------------------

# Global embedding scores — populated once at startup if sentence-transformers
# is available, then used inside score_semantic instead of TF-IDF
EMBEDDING_SCORES: dict = {}

JD_FOR_EMBEDDING = """
Senior AI Engineer role at a Series A AI startup in India. 
Requires production experience with embeddings, vector databases, semantic search, 
retrieval and ranking systems. Strong Python. NLP, information retrieval, 
LLM fine-tuning, evaluation frameworks NDCG MRR. Sentence transformers, FAISS, 
Pinecone, Elasticsearch, OpenSearch, Weaviate, Qdrant. Hybrid search, dense retrieval.
Recommendation systems, candidate job matching. Product company experience, 
not consulting. Ship fast, iterate. 5-9 years experience. Pune Noida Hyderabad 
Mumbai Delhi India locations preferred.
"""

def build_embedding_scores(candidates: list) -> dict:
    cache_path = Path("embeddings_cache.pkl")

    # Load from cache if it exists
    if cache_path.exists():
        print("Loading embeddings from cache...")
        import pickle
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        import pickle
        print("sentence-transformers imported successfully")
    except ImportError as e:
        print(f"Import failed: {e}")
        return {}

    print("Loading sentence-transformers model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    jd_vec = model.encode(JD_FOR_EMBEDDING, normalize_embeddings=True)

    print("Encoding 100K candidate profiles (this takes 3-4 mins)...")
    texts = [build_candidate_text(c) for c in candidates]
    vecs  = model.encode(
        texts,
        batch_size=256,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    scores = {}
    for i, c in enumerate(candidates):
        sim = float(np.dot(vecs[i], jd_vec))
        scores[c["candidate_id"]] = max(sim, 0.0)

    print("Embeddings done. Saving to cache...")
    with open(cache_path, "wb") as f:
        pickle.dump(scores, f)
    print("Cache saved.")

    return scores

def score_semantic(candidate: dict) -> tuple:
    cid   = candidate["candidate_id"]
    notes = []

    # Use embedding cosine similarity if available
    if cid in EMBEDDING_SCORES:
        score = round(EMBEDDING_SCORES[cid], 4)
        if score >= 0.45:
            notes.append(f"strong semantic match (embedding {score:.2f})")
        elif score >= 0.30:
            notes.append(f"moderate semantic match (embedding {score:.2f})")
        else:
            notes.append(f"weak semantic match (embedding {score:.2f})")
        return score, notes

    # Fallback: TF-IDF token overlap
    text        = build_candidate_text(candidate)
    cand_tokens = set(text.split())

    if not cand_tokens:
        return 0.0, ["no text content"]

    overlap = len(JD_TERMS & cand_tokens)
    score   = min(
        overlap / (math.sqrt(len(JD_TERMS)) * math.sqrt(max(len(cand_tokens), 1))) * 3.5,
        1.0
    )

    if overlap >= 15:
        notes.append(f"strong JD text overlap ({overlap} terms)")
    elif overlap >= 7:
        notes.append(f"moderate JD text overlap ({overlap} terms)")
    else:
        notes.append(f"weak JD text overlap ({overlap} terms)")

    return round(score, 4), notes
# ---------------------------------------------------------------------------
# FINAL SCORER
# ---------------------------------------------------------------------------

def score_candidate(candidate: dict) -> tuple:
    # Honeypot check first — eliminated candidates get score 0
    if is_honeypot(candidate):
        return 0.0, "honeypot: impossible profile detected"

    # Run all five components
    semantic_score, semantic_notes = score_semantic(candidate)
    career_score,   career_notes   = score_career(candidate)
    skills_score,   skills_notes   = score_skills(candidate)
    signal_score,   signal_notes   = score_signals(candidate)
    edu_score,      edu_notes      = score_education(candidate)

    # Weighted combination
    final = (
        WEIGHT_SEMANTIC   * semantic_score +
        WEIGHT_CAREER     * career_score   +
        WEIGHT_SKILLS     * skills_score   +
        WEIGHT_SIGNALS    * signal_score   +
        WEIGHT_EDUCATION  * edu_score
    )
    final = round(min(max(final, 0.0), 1.0), 4)

    # Build reasoning string — specific, honest, pulled from actual scorer notes
    # Build reasoning string — specific per candidate
    profile  = candidate["profile"]
    yoe      = profile["years_of_experience"]
    title    = profile["current_title"]
    company  = profile["current_company"]
    location = profile["location"]
    sig      = candidate["redrob_signals"]

    # Pull the single most informative career note
    career_highlight = next(
        (n for n in career_notes if "strong production" in n or "prior AI" in n or "strong title" in n),
        career_notes[0] if career_notes else ""
    )

    # Pull the single most informative signal note
    signal_highlight = next(
        (n for n in signal_notes if any(x in n for x in [
            "immediately", "notice", "active this week", "active ", "target location", "response rate"
        ])),
        signal_notes[0] if signal_notes else ""
    )

    # Pull top matched skills
    skills_highlight = next(
        (n for n in skills_notes if "relevant skills" in n),
        ""
    )

    reasoning = (
        f"{title} at {company}, {yoe:.1f} yrs, {location}. "
        f"{career_highlight}. "
        f"{skills_highlight}. "
        f"{signal_highlight}."
    )

    # Clean up double periods and extra spaces
    
    reasoning = re.sub(r'\.\s*\.', '.', reasoning)
    reasoning = re.sub(r'\s+', ' ', reasoning).strip()
    reasoning = reasoning[:220]

    return final, reasoning


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="GhostProtocol Candidate Ranker")
    parser.add_argument("--candidates", default="candidates.jsonl")
    parser.add_argument("--out", default="submission/recruitiq.csv")
    parser.add_argument("--no-embeddings", action="store_true",
                        help="Skip sentence-transformers, use TF-IDF. Runs in ~60s on CPU, no GPU needed.")
    args = parser.parse_args()

    candidates = load_candidates(args.candidates)
    global EMBEDDING_SCORES
    if not args.no_embeddings:
        EMBEDDING_SCORES = build_embedding_scores(candidates)
    else:
        print("Skipping embeddings. Using TF-IDF fallback.")
        
    # Score all candidates
    print("Scoring candidates...")
    results = []
    for i, candidate in enumerate(candidates):
        if i % 10000 == 0 and i > 0:
            print(f"  {i:,} / {len(candidates):,}...")

        score, reasoning = score_candidate(candidate)
        results.append({
            "candidate_id": candidate["candidate_id"],
            "score":        score,
            "reasoning":    reasoning,
        })

    # Sort by score descending, break ties by candidate_id ascending
    results.sort(key=lambda x: (-x["score"], x["candidate_id"]))

    # Take top 100 and assign ranks
    top100 = results[:100]
    for i, r in enumerate(top100):
        r["rank"] = i + 1

    # Ensure scores are non-increasing (fix floating point edge cases)
    for i in range(1, len(top100)):
        if top100[i]["score"] > top100[i - 1]["score"]:
            top100[i]["score"] = top100[i - 1]["score"]

    # Write CSV
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in top100:
            writer.writerow([
                r["candidate_id"],
                r["rank"],
                f"{r['score']:.4f}",
                r["reasoning"]
            ])

    print(f"\nDone. Written to {out_path}")
    print(f"Score range: {top100[0]['score']:.4f} (rank 1) → {top100[-1]['score']:.4f} (rank 100)")
    print("\nTop 10:")
    for r in top100[:10]:
        print(f"  [{r['rank']:>3}] {r['candidate_id']} | {r['score']:.4f} | {r['reasoning'][:80]}")


if __name__ == "__main__":
    main()