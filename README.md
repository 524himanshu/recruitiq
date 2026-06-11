# RecruitIQ — Intelligent Candidate Discovery

**Team:** GhostProtocol  
**Hackathon:** Redrob India Runs — Track 1: Data & AI Challenge  
**Problem:** Rank 100,000 candidates against a Senior AI Engineer job description using intelligent multi-signal scoring.

---

## Approach

We built a five-component weighted scoring system that goes beyond keyword matching to evaluate candidates the way a great recruiter would.

### Scoring Components

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| Semantic Similarity | 20% | Embedding-based cosine similarity between candidate text and JD using `all-MiniLM-L6-v2` |
| Career Fit | 28% | Title relevance, production ML signals in job descriptions, consulting-only penalty, company size and industry |
| Skills Match | 17% | Required skills weighted by proficiency, endorsements, duration, and Redrob assessment scores |
| Behavioral Signals | 30% | Platform activity, notice period, recruiter response rate, GitHub activity, location fit, salary fit |
| Education Tier | 5% | Institution tier (tier_1 through tier_4) from candidate education history |

### Key Design Decisions

**Consulting-only penalty:** Candidates whose entire career history is at consulting firms (TCS, Infosys, Wipro, etc.) receive a 0.25x multiplier on career score. The JD explicitly disqualifies this background.

**Keyword stuffer detection:** Candidates with 6+ matched AI skills but a non-AI title and no ML signals in their career descriptions receive a 0.35x skills score penalty.

**Honeypot detection:** Three checks flag impossible profiles — a single job longer than total career, expert skills with zero usage months, and YOE inconsistent with career history.

**Behavioral signals weighted highest:** A perfect-on-paper candidate who hasn't logged in for 6 months and has a 5% recruiter response rate is not actually available. Signals reflect real hiring intent.

**Salary fit scoring:** Candidates whose expected salary range overlaps with a Series A Senior AI Engineer budget (25–55 LPA) receive a positive signal. Candidates above budget are penalized.

---

## Setup

```bash
# Clone the repo
git clone https://github.com/524himanshu/recruitiq
cd recruitiq

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

---

## Run

```bash
python rank.py --candidates candidates.jsonl --out submission/recruitiq.csv
```

First run downloads and caches embeddings (~4 mins on GPU, ~25 mins on CPU).  
Subsequent runs load from cache and complete in under 60 seconds.

---

## Validate

```bash
python validate_submission.py submission/recruitiq.csv
```

---

## Project Structure

```
recruitiq/
├── rank.py                    # Main ranking script
├── explore.py                 # Data exploration utility
├── requirements.txt           # Dependencies
├── submission/
│   └── recruitiq.csv          # Ranked output (top 100)
├── sandbox/
│   └── app.py                 # Streamlit demo
└── README.md
```

## Results

Score range: 0.8386 (rank 1) → 0.7008 (rank 100)

Top 5 candidates:
1. Senior NLP Engineer at Niramai — 7.8 yrs, Indore
2. Search Engineer at Sarvam AI — 7.6 yrs, Gurgaon
3. Senior ML Engineer at Zomato — 7.2 yrs, Noida
4. Senior ML Engineer at Genpact AI — 6.1 yrs, Pune
5. AI Engineer at upGrad — 7.6 yrs, Indore

