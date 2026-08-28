# Sodio Interest Graph POC 🕸️

A full-stack Proof-of-Concept demonstrating the **Interest Graph Engine** for an interest-driven community platform. The system decides user feed rankings, club recommendations, local vendor matches, and event suggestions.

Built with a **React (TypeScript) Frontend** and a **FastAPI (Python) Backend**, utilizing **NVIDIA NIM APIs** for structured NLP classification and **pure Python execution** for mathematical ranking formulas.

---

## 🚀 Key Features & Architectural Decisions

### 1. Hybrid Storage Strategy (POC Simulation)
- **Relational Source-of-Truth**: Implemented via **SQLite** (using SQLAlchemy) storing users, posts, clubs, businesses, events, and interactions.
- **Graph Traversal**: Simulated in-memory using **NetworkX** (modeling `HAS_INTEREST`, `MEMBER_OF`, `FOLLOWS`, `ENGAGED_WITH`, and `SIMILAR_TO` relations up to 3 BFS hops).
- **Vector Space Similarity**: Matrix representations and **cosine similarity** computed locally using **NumPy** vectors.

### 2. Critical Engineering Constraint (No Math in LLMs)
100% of mathematical formulas, volumetric calculations, decaying functions, PageRank trust propagations, and re-rankings execute in **native Python**.
- **NVIDIA NIM** is **ONLY** called for:
  - Extracting interest tags from post text using `meta/llama-3.1-70b-instruct` (Structured JSON output via Pydantic).
  - Optional semantic vector generation using `nvidia/nv-embedqa-e5-v5`.
- **All ranking scoring** is strictly Python-governed.

### 3. Ranking Engine Algorithms (Pure Python)
- **PageRank-Style Trust Propagation**: Accounts vouching for others propagates trust.
  $$trust[v]_{t+1} = (1 - d) + d \sum_{u \in pred(v)} \frac{trust[u]}{out\_degree[u]}$$
- **Time decay (recency factor)**:
  $$recency\_factor = e^{-\lambda \times days\_since\_interaction}$$
- **Multi-Factor Score**:
  $$score = w_1 Relevance + w_2 Trust + w_3 Authority + w_4 Freshness + w_5 Proximity + w_6 Engagement - SpamRisk$$
- **MMR Diversity Re-ranking**:
  $$MMR(d) = \lambda \cdot relevance(d) - (1-\lambda) \cdot \max_{s \in Selected} Sim(d, s)$$
- **Commercial Content Slot Budget**: Structural rule capping business / advertisement content to at most **20% of the feed**.

---

## 📁 Directory Structure

```
sodio-interest-graph/
├── backend/                    # Python FastAPI service
│   ├── app/
│   │   ├── api/               # Router endpoints (feed, graph, metrics, etc.)
│   │   ├── core/              # Config & logging setups
│   │   ├── db/                # DB setup & seed dataset script
│   │   ├── models/            # SQLAlchemy models & Pydantic schemas
│   │   ├── services/          # Pure Python engines (ranking, trust, graph)
│   │   └── main.py            # FastAPI main entry bootstrap
│   ├── .env                   # Configuration & API Keys
│   └── requirements.txt       # Dependencies
├── frontend/                  # React + Vite + Tailwind CSS + Vis.js
│   ├── src/
│   │   ├── api/               # API clients
│   │   ├── components/        # FeedCard, ScoreBreakdown, Graph canvas renderer
│   │   ├── pages/             # Dashboard, Discovery, GraphExplorer, Analytics
│   │   ├── types/             # TypeScript types matching Pydantic
│   │   ├── App.tsx            # State router container
│   │   └── main.tsx           # React mounting entry
│   ├── .env                   # API URL config
│   └── package.json           # Frontend packages
└── scripts/                   # Set-up scripts for external databases
    ├── setup-neo4j-windows.bat
    ├── setup-neo4j-ubuntu.sh
    ├── setup-neo4j-mac.sh
    ├── setup-milvus-windows.bat
    ├── setup-milvus-ubuntu.sh
    └── setup-milvus-mac.sh
```

---

## 🛠️ Set-up Instructions

### Prerequisites
- Python 3.12+ (supports Python 3.14)
- Node.js 18+ & NPM
- NVIDIA NIM API Key (obtain from [build.nvidia.com](https://build.nvidia.com))

### 1. Backend Server Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install numpy --only-binary :all:
   pip install -r requirements.txt
   ```
4. Copy/Create your `.env` configuration file inside `backend/` and insert your **NVIDIA API Key**:
   ```env
   NVIDIA_API_KEY=your_nvidia_nim_key_here
   DATABASE_URL=sqlite:///./sodio.db
   DEBUG=true
   ```
5. Run the server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   The backend auto-seeds itself on startup with 5 domains, 15 interests, 5 users with populated vectors, and post content.

### 2. Frontend Setup
1. Open a new terminal in the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
4. Open your browser to `http://localhost:5173`.

---

## 🪵 Interactive Verbose Logging
Every calculation step, similarity dot product, decay multiplier, and LLM communication payload is fully logged with detailed traces in standard output and the persistent log file `sodio_backend.log`.

Example log output during feed scoring:
```log
2026-08-28T22:15:32 | DEBUG    | app.services.feed_ranker.compute_freshness_score:42 | hours_old=2.12 | days_old=0.0883 | freshness=exp(-0.10*0.0883)=0.991207
2026-08-28T22:15:32 | DEBUG    | app.services.interest_engine.compute_cosine_similarity:182 | dot_product = 2.000000 | |a|=1.732050 | |b|=1.414213 | similarity = 0.816497
2026-08-28T22:15:32 | DEBUG    | app.services.feed_ranker.compute_final_score:192 | score = (0.30×0.816) + (0.20×0.820) + (0.15×0.700) + (0.15×0.991) + (0.10×0.500) + (0.05×0.120) + (0.05×0.500) - 0.000 = 0.7412
```

---

## 📦 Setting Up Production Databases (Neo4j / Milvus)
If transitioning from this POC simulation to production-level infrastructure, run the target script located under `scripts/` matching your OS:
- **Windows**: `scripts/setup-neo4j-windows.bat` & `scripts/setup-milvus-windows.bat`
- **Ubuntu**: `scripts/setup-neo4j-ubuntu.sh` & `scripts/setup-milvus-ubuntu.sh`
- **macOS**: `scripts/setup-neo4j-mac.sh` & `scripts/setup-milvus-mac.sh`
These scripts handle fetching binaries, managing daemon services, or spinning up docker-containers automatically.
# Interest-graph
