import streamlit as st
import json
import math
import re
from datetime import date, datetime

st.set_page_config(
    page_title="RecruitIQ — Intelligent Candidate Ranking",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 RecruitIQ")
st.caption("Intelligent candidate ranking beyond keyword filters — Team GhostProtocol")

# ---------------------------------------------------------------------------
# Paste scoring constants and functions from rank.py
# ---------------------------------------------------------------------------

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

AI_TITLE_KEYWORDS = [
    "ai engineer", "ml engineer", "machine learning engineer", "applied scientist",
    "nlp engineer", "search engineer", "ranking engineer", "data scientist",
    "applied ml", "recommendation", "retrieval", "research scientist",
    "senior engineer", "staff engineer", "principal engineer"
]

CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "hcl", "tech mahindra", "mphasis", "hexaware", "ltimindtree", "mindtree",
    "birlasoft", "persistent systems", "coforge", "niit technologies",
}

TARGET_LOCATIONS = {
    "pune", "noida", "mumbai", "hyderabad", "delhi", "gurgaon",
    "gurugram", "bangalore", "bengaluru", "ncr", "indore", "ahmedabad"
}

PROFICIENCY_WEIGHT = {
    "beginner": 0.25, "intermediate": 0.55,
    "advanced": 0.80, "expert": 1.0
}

PRODUCTION_ML_KEYWORDS = [
    "deployed", "production", "serving", "inference", "pipeline",
    "embedding", "retrieval", "ranking", "search", "recommendation",
    "vector", "index", "latency", "throughput", "scale", "real-time",
    "a/b test", "evaluation", "ndcg", "mrr", "fine-tun", "rag",
    "rerank", "recall", "precision", "benchmark", "experiment"
]

TODAY = date.today()

WEIGHT_SEMANTIC   = 0.20
WEIGHT_CAREER     = 0.28
WEIGHT_SKILLS     = 0.17
WEIGHT_SIGNALS    = 0.30
WEIGHT_EDUCATION  = 0.05


def score_career(candidate):
    profile = candidate["profile"]
    career  = candidate["career_history"]
    score   = 0.0
    yoe     = profile["years_of_experience"]

    if 5 <= yoe <= 9:       score += 0.25
    elif 4 <= yoe <= 12:    score += 0.10
    elif yoe > 12:          score += 0.08
    else:                   score += 0.03

    all_companies   = [j["company"].lower() for j in career]
    consulting_jobs = sum(1 for c in all_companies if any(f in c for f in CONSULTING_FIRMS))
    if consulting_jobs == len(career) and career:
        return round(score * 0.25, 4)

    for kw in AI_TITLE_KEYWORDS:
        if kw in profile.get("current_title", "").lower():
            score += 0.25
            break

    prod_hits = sum(
        1 for job in career
        for kw in PRODUCTION_ML_KEYWORDS
        if kw in job.get("description", "").lower()
    )
    score += min(prod_hits / 12.0, 1.0) * 0.30

    size = profile.get("current_company_size", "")
    if size in ["51-200", "201-500", "501-1000"]: score += 0.08
    elif size in ["1001-5000"]:                    score += 0.04

    industry = profile.get("current_industry", "").lower()
    if any(i in industry for i in ["technology","software","ai","fintech","saas","ml"]):
        score += 0.06

    return round(min(score, 1.0), 4)


def score_skills(candidate):
    skills = candidate["skills"]
    if not skills:
        return 0.0
    total = 0.0
    matched = 0
    for s in skills:
        name = s["name"].lower()
        if not any(req in name or name in req for req in REQUIRED_SKILLS):
            continue
        base          = PROFICIENCY_WEIGHT.get(s.get("proficiency","beginner"), 0.25)
        endorse_mult  = 1.0 + min(math.log1p(s.get("endorsements",0)) / 8.0, 0.35)
        duration_mult = 1.0 + min(s.get("duration_months",0) / 60.0, 0.40)
        total += base * endorse_mult * duration_mult
        matched += 1
    return round(min(total / 10.0, 1.0), 4)


def score_signals(candidate):
    sig     = candidate["redrob_signals"]
    profile = candidate["profile"]
    score   = 0.0

    if sig["open_to_work_flag"]: score += 0.12

    try:
        days = (TODAY - datetime.strptime(sig["last_active_date"], "%Y-%m-%d").date()).days
        if days <= 7:    score += 0.20
        elif days <= 30: score += 0.15
        elif days <= 90: score += 0.08
        elif days <= 180: score += 0.02
        else:            score -= 0.10
    except: pass

    notice = sig.get("notice_period_days", 90)
    if notice == 0:      score += 0.15
    elif notice <= 30:   score += 0.12
    elif notice <= 60:   score += 0.06
    elif notice <= 90:   score += 0.02

    score += sig.get("recruiter_response_rate", 0) * 0.15
    score += sig.get("interview_completion_rate", 0) * 0.08

    github = sig.get("github_activity_score", -1)
    if github >= 0: score += (github / 100.0) * 0.12

    score += (sig.get("profile_completeness_score", 0) / 100.0) * 0.05

    location = profile.get("location", "").lower()
    country  = profile.get("country", "").lower()
    relocate = sig.get("willing_to_relocate", False)

    if country == "india" and any(loc in location for loc in TARGET_LOCATIONS):
        score += 0.12
    elif country == "india" and relocate: score += 0.06
    elif country == "india":              score += 0.03
    elif country != "india" and not relocate: score -= 0.12

    sal = sig.get("expected_salary_range_inr_lpa", {})
    sal_min, sal_max = sal.get("min", 0), sal.get("max", 0)
    if sal_min > 0 and sal_max > 0:
        overlap = min(sal_max, 55) - max(sal_min, 25)
        if overlap >= 0:
            score += min((overlap / max(sal_max - sal_min, 1)) * 0.08, 0.08)
        elif sal_min > 55:
            score -= 0.08

    return round(min(max(score, 0.0), 1.0), 4)


def score_education(candidate):
    tiers = {"tier_1": 1.0, "tier_2": 0.65, "tier_3": 0.35, "tier_4": 0.15}
    best  = 0.0
    for edu in candidate.get("education", []):
        best = max(best, tiers.get(edu.get("institution_tier", ""), 0.0))
    return round(best, 4)


def score_semantic_tfidf(candidate, jd_terms):
    parts = [
        candidate["profile"].get("headline",""),
        candidate["profile"].get("summary",""),
        candidate["profile"].get("current_title",""),
    ]
    for job in candidate["career_history"]:
        parts.append(job.get("description",""))
    for s in candidate["skills"]:
        parts.append(s["name"])
    text   = " ".join(parts).lower()
    tokens = set(text.split())
    overlap = len(jd_terms & tokens)
    score = overlap / (math.sqrt(len(jd_terms)) * math.sqrt(max(len(tokens),1))) * 3.5
    return round(min(score, 1.0), 4)


def score_candidate(candidate, jd_terms):
    sem  = score_semantic_tfidf(candidate, jd_terms)
    car  = score_career(candidate)
    ski  = score_skills(candidate)
    sig  = score_signals(candidate)
    edu  = score_education(candidate)
    final = (
        WEIGHT_SEMANTIC  * sem +
        WEIGHT_CAREER    * car +
        WEIGHT_SKILLS    * ski +
        WEIGHT_SIGNALS   * sig +
        WEIGHT_EDUCATION * edu
    )
    return round(min(max(final, 0.0), 1.0), 4)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Job Description")
    jd_text = st.text_area(
        "Paste the job description here",
        height=300,
        placeholder="Senior AI Engineer...",
        label_visibility="collapsed"
    )

with col2:
    st.subheader("Candidates")
    uploaded = st.file_uploader(
        "Upload candidates (.jsonl — max 500 candidates for demo)",
        type=["jsonl", "json"]
    )

st.divider()

if st.button("🚀 Rank Candidates", type="primary", use_container_width=True):
    if not jd_text.strip():
        st.error("Paste a job description first.")
    elif not uploaded:
        st.error("Upload a candidates file first.")
    else:
        with st.spinner("Scoring candidates..."):
            # Parse candidates
            candidates = []
            content = uploaded.read().decode("utf-8")
            for line in content.strip().split("\n"):
                line = line.strip()
                if line:
                    try:
                        candidates.append(json.loads(line))
                    except:
                        pass

            if not candidates:
                st.error("No valid candidates found in file.")
            else:
                # Build JD terms
                jd_terms = set(jd_text.lower().split())

                # Score all candidates
                results = []
                for c in candidates:
                    score = score_candidate(c, jd_terms)
                    p     = c["profile"]
                    sig   = c["redrob_signals"]
                    results.append({
                        "Rank":        0,
                        "ID":          c["candidate_id"],
                        "Name/Title":  p.get("current_title", ""),
                        "Company":     p.get("current_company", ""),
                        "Location":    p.get("location", ""),
                        "YOE":         p.get("years_of_experience", 0),
                        "Notice (days)": sig.get("notice_period_days", 0),
                        "Response Rate": f"{sig.get('recruiter_response_rate', 0):.0%}",
                        "Score":       score,
                    })

                results.sort(key=lambda x: -x["Score"])
                for i, r in enumerate(results):
                    r["Rank"] = i + 1

                top_n = min(100, len(results))
                st.success(f"Ranked {len(results):,} candidates. Showing top {top_n}.")

                # Metrics row
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Total Candidates", f"{len(results):,}")
                m2.metric("Top Score", f"{results[0]['Score']:.4f}")
                m3.metric("Rank 1", results[0]['Company'])
                m4.metric("Rank 1 Notice", f"{results[0]['Notice (days)']}d")

                st.subheader("Top Candidates")
                st.dataframe(
                    results[:top_n],
                    width=True,
                    hide_index=True,
                    column_config={
                        "Score": st.column_config.ProgressColumn(
                            "Score", min_value=0, max_value=1, format="%.4f"
                        ),
                        "YOE": st.column_config.NumberColumn("YOE", format="%.1f yrs"),
                    }
                )