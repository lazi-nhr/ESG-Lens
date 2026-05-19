# esg rag system

A Retrieval Augmented Generation (RAG) system for ESG Reporting.

## Quick start

### 1. Start the database

Just start the database app. You might need to connect to it from another container to set up your DB schema, or you might you an ORM and a migrator (such as sqlalchemy and alembic in python or prisma for nodejs/typescript for example).

### 2. Install dependencies

```bash
cd backend                 # navigate to backend root

pip install -r requirements.txt
```

### 2a. Full Stack Running

```bash
cd /path/to/esg-reporting-rag-system  # navigate to project root

python setup.py                       # checks DB, loads sample data, starts both servers

python cleanup.py                     # stops servers, clears documents, removes logs
```

(Bash equivalents: `./setup.sh` / `./cleanup.sh`)

### 2b. Backend Running

In the backend app:

```bash
cd backend                  # navigate to backend root

python main.py              # starts on port 8500
# or
python start_backend.py     # checks DB, starts FastAPI on port 8500

python stop_backend.py      # stops server
```


### 2c. Frontend Running

In the frontend app:

```bash
cd frontend

python start_frontend.py    # starts reverse-proxy server on port 3000

python stop_frontend.py     # stops server
```

### 3. Open Frontend

Open the VS Code Server URL for port 3000 in your browser.

1. In the bottom panel of your VS Code interface (where you see the Terminal), look for a tab labeled Ports.

2. Look for the row where the Port is 3000.

3. Click the link in the "Forwarded Address" column.


### 4. View logs

```bash
tail -f /tmp/backend.log
tail -f /tmp/frontend.log
```

## How networking works on Nuvolos

Nuvolos runs your applications as **pods** inside Kubernetes. You don't manage
Kubernetes directly — Nuvolos handles that. Here's what matters:

- Each pod can contain one or more **containers** (processes).
- Nuvolos places every pod on a **managed internal subnet** — a private network
  that only your pods can see.
- Each pod's main container gets a **hostname** (e.g. `nv-service-abc123...`).
  Other pods reach it by that hostname, the same way computers on a LAN find
  each other by name. In order for a pod to even get a hostname, you have to turn this feature on. See the [docs](https://docs.nuvolos.com/features/applications/configuring-applications#connecting-to-apps-from-other-applications)
- **Nothing on this internal network is directly reachable from the internet.**
  The only way an outside browser can talk to your app is through Nuvolos'
  built-in **reverse proxy** (the VS Code Server URL it gives you).

### What is a reverse proxy?

A **reverse proxy** sits between external users and your internal services.
The user's browser talks to the proxy; the proxy forwards the request to
the right internal service and returns the response.

```
 Internet                          Nuvolos internal network
──────────                         ────────────────────────

Browser                            ┌──────────────────────┐
   │                               │  Frontend  (port 3000)│
   │  HTTPS request                │  - serves index.html  │
   ├──────────────────────────────►│  - reverse-proxies    │
   │  (goes through Nuvolos'       │    /documents, /query │
   │   VS Code Server proxy)       │    to the Backend     │
   │                               └──────────┬───────────┘
   │                                          │ http://<BACKEND_HOSTNAME>:8500
   │                               ┌──────────▼───────────┐
   │                               │  Backend   (port 8500)│
   │                               │  - FastAPI app        │
   │                               │  - talks to Postgres  │
   │                               └──────────┬───────────┘
   │                                          │ postgresql://<DB_HOSTNAME>:5432
   │                               ┌──────────▼───────────┐
   │                               │  PostgreSQL + pgvector│
   │                               │  (vector similarity)  │
   │                               └──────────────────────┘
```

**Why does the frontend reverse-proxy API calls instead of letting the browser
call the backend directly?**

Because the backend hostname (e.g. `nv-service-abc123...`) only exists on the
internal Nuvolos network. Your browser, sitting on the public internet, cannot
resolve or reach it. So the frontend server accepts the API request from the
browser and forwards it to the backend over the internal network. This is
exactly what tools like Nginx and API gateways do in production.

## How the pieces fit together

| Component | Port | Hostname | Role |
|-----------|------|----------|------|
| Frontend  | 3000 | this pod | Serves HTML; **reverse-proxies** `/health`, `/documents`, `/query` to the backend |
| Backend   | 8500 | set by Nuvolos (`BACKEND_HOST` env var) | FastAPI app — stores docs, runs vector search |
| PostgreSQL| 5432 | set by Nuvolos (`DB_HOST` env var) | Database with `pgvector` extension |

The frontend decides what to proxy based on the URL path:

| Browser requests…       | Frontend does…                     |
|------------------------|------------------------------------|
| `/` or `/index.html`  | Serves the static HTML page        |
| `/health`              | Forwards to `backend:8500/health`  |
| `/documents`           | Forwards to `backend:8500/documents` |
| `/query`               | Forwards to `backend:8500/query`   |
| `/evaluate`            | Forwards to `backend:8500/evaluate` |

## API endpoints

| Method | Path         | Description              |
|--------|-------------|--------------------------|
| GET    | `/`         | Root / status            |
| GET    | `/health`   | Health check (DB ping)   |
| POST   | `/documents`| Add a document           |
| GET    | `/documents`| List all documents       |
| POST   | `/query`    | Vector-similarity search |
| EVALUATE | `/evaluate` | Run RAG evaluation     |

Test from the terminal (inside the backend pod, or any pod on the same subnet):

```bash
curl http://localhost:8500/health

curl -X POST http://localhost:8500/documents \
  -H "Content-Type: application/json" \
  -d '{"content":"Python is a high-level programming language."}'

curl -X POST http://localhost:8500/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is Python?","top_k":3}'
```

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # API routes (health, documents, query, evaluate)
│   │   ├── core/             # Configuration and error handling
│   │   ├── db/               # Database connection, schemas, repositories
│   │   ├── llm/              # LLM integration for answer generation
│   │   ├── retrieval/        # Vector search and similarity retrieval
│   │   ├── services/         # Business logic (evaluate_service)
│   │   ├── formatting/       # Report formatting and rendering
│   │   └── main.py           # FastAPI app setup
│   ├── scripts/
│   │   ├── query_esg_evaluation.py   # API-based query script
│   │   ├── query_database.py         # Direct database query script
│   │   ├── batch_evaluate.py         # Batch evaluation script
│   │   ├── seed_db.py                # Load PDFs into database
│   │   ├── cli.py                    # CLI utilities
│   │   ├── evaluations_example.json  # Example evaluation configs
│   │   ├── quickstart.sh             # Interactive quick-start menu
│   │   └── README.md                 # Query scripts documentation
│   ├── main.py               # Entry point (imports from app.main)
│   ├── requirements.txt       # Python dependencies
│   ├── start_backend.py       # Start script (checks DB, launches server on :8500)
│   └── stop_backend.py        # Stop script
├── frontend/
│   ├── index.html            # Single-page UI
│   ├── server.py             # HTTP server + reverse proxy to backend
│   ├── start_frontend.py      # Start script (launches server on :3000)
│   └── stop_frontend.py       # Stop script
├── data/
│   ├── raw_pdfs/             # PDF documents for seeding the database
│   └── sample_data.csv        # Sample ESG documents (loaded on first run)
├── setup.py / setup.sh        # One-command full-stack setup
├── cleanup.py / cleanup.sh    # One-command full-stack teardown
├── STORY.md                   # Narrative walkthrough
└── README.md                  # This file
```

## Query Scripts

The `backend/scripts/` directory contains command-line tools for querying the ESG database:

- **query_esg_evaluation.py** - HTTP API client for the FastAPI backend
- **query_database.py** - Direct database queries with vector/full-text search
- **batch_evaluate.py** - Batch process multiple companies and criteria
- **quickstart.sh** - Interactive menu to run example queries

See [backend/scripts/README.md](backend/scripts/README.md) for detailed usage and examples.

## Technical notes

### Embeddings

The system uses **Sentence Transformers** (all-MiniLM-L6-v2, 384 dimensions) for document and query embeddings. Switch models in `app/core/config.py`:

```python
# In requirements.txt: sentence-transformers==3.0.1
# In config: EMBEDDING_MODEL = "all-MiniLM-L6-v2" or any HuggingFace model
```

For production, consider:
- Larger models (all-mpnet-base-v2, 768 dim) for better quality
- OpenAI embeddings API for superior performance
- Cached embeddings for faster inference

### LLM Integration

The system supports multiple LLM providers via `app/llm/generator.py`:

- **HuggingFace Inference API** (default, configurable via `HF_API_KEY`)
- **OpenAI** (swap `generate_answer()` implementation)
- **Open-source models** (Mistral, Llama via HuggingFace)

Configure in `.env`:
```bash
LLM_PROVIDER=huggingface
HF_MODEL=gpt2
HF_API_KEY=your_api_key_here
```

### Vector Database

Uses **PostgreSQL + pgvector** for:
- Vector similarity search (cosine distance)
- Hybrid search (vector + full-text keywords)
- Indexed HNSW for sub-second search on millions of documents

### Evaluation Reports

The `/evaluate` endpoint generates structured ESG reports with:
- Retrieved document context
- LLM-generated assessment
- Markdown or plain-text formatting
- Configurable output per company/criterion

## Database Management

### Initialize Database

The database is automatically initialized on first run:

```bash
python setup.py  # Initializes DB, creates tables, loads sample data
```

Or manually:

```bash
cd backend
python start_backend.py  # Creates tables on startup if they don't exist
```

### Seed with Documents

Load PDF documents into the database:

```bash
cd backend/scripts
python seed_db.py  # Loads all PDFs from data/raw_pdfs/
```

### Clear Documents

Delete all documents but keep tables:

```bash
python -c "
import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, database='nuvolos', user='nuvolos', password='nuvolos')
cur = conn.cursor()
cur.execute('DELETE FROM documents;')
conn.commit()
cur.close()
conn.close()
print('✅ All documents deleted')
"
```

### Reset Database

Drop and recreate all tables:

```bash
python cleanup.py  # Stops servers, clears all data, removes logs
python setup.py    # Reinitializes and starts fresh
```
