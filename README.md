Customer Support AI Agent (support-agent)
A production-grade, secure, and deterministic customer support AI agent built with FastAPI, OpenAI, SQLAlchemy, and Pydantic. This architecture prioritizes security, policy enforcement, transactional integrity (idempotency), and auditability for enterprise e-commerce platforms.

🏗️ Architectural Highlights
Deterministic Policy Engine: Enforces strict business rules (e.g., 30-day return windows, order status validation) programmatically rather than relying purely on LLM reasoning.

Human-in-the-Loop (HITL) Workflow: Automatically flags high-value financial requests exceeding $100.00 for supervisor review (PENDING_APPROVAL).

Idempotency Protection: Prevents duplicate financial transactions and double writes during network retries using unique idempotency keys.

Immutable Audit Logging: Middleware and service layers record all tool executions, API requests, timing, actor metadata, and outcomes.

Secure Tool Allowlisting: Strict Pydantic argument validation and function-calling schemas prevent unauthorized actions or prompt injection exploits.

🛠️ Tech Stack
Language: Python 3.11+

Package Management: uv

API Framework: FastAPI, Uvicorn

Database & ORM: SQLite, SQLAlchemy

Validation & Settings: Pydantic v2, pydantic-settings

Authentication: JWT (python-jose)

Testing: pytest

Containerization: Docker & Docker Compose

📂 Project Structure
Plaintext
support-agent/
├── app/
│   ├── api/
│   │   ├── endpoints.py        # FastAPI REST routes (chat, refunds, supervisor decisions)
│   │   └── middleware.py       # Immutable audit logging middleware
│   ├── core/
│   │   ├── config.py           # Centralized Pydantic settings & env variables
│   │   ├── database.py         # SQLAlchemy engine and sessionmaker setup
│   │   └── security.py         # JWT authentication & role-based dependencies
│   ├── models/
│   │   └── database_models.py  # SQLAlchemy ORM models (Customer, Order, Refund, AuditLog)
│   ├── schemas/
│   │   └── agent_schemas.py    # Pydantic validation models for requests/responses
│   ├── services/
│   │   ├── policy_engine.py    # Deterministic business policy rules
│   │   ├── refund_service.py   # Refund lifecycles & idempotency state machine
│   │   └── audit_service.py    # Immutable audit logging service
│   ├── init_db.py              # Database initialization script
│   └── main.py                 # FastAPI application entrypoint
├── agent/
│   ├── prompt.py               # System prompts, security guardrails & constraints
│   ├── tools.py                # Allowlisted tool registry & argument validators
│   └── runner.py               # LLM loop orchestration & iteration limiter
├── tests/
│   ├── test_agent_tools.py     # Integration tests for tool execution & guardrails
│   ├── test_idempotency.py     # Tests for duplicate write prevention
│   └── test_support_agent.py   # Policy engine unit tests
├── Dockerfile                  # Multi-stage production Dockerfile using uv
├── docker-compose.yml          # Container orchestration with persistent volumes
├── pyproject.toml              # Dependency definitions
└── README.md
🚀 Getting Started & Installation
Prerequisites
Python 3.11+

Astral uv package manager

Docker & Docker Compose (optional for containerized deployment)

1. Clone and Install Dependencies
Bash
git clone https://github.com/your-org/support-agent.git
cd support-agent

# Install dependencies using uv
uv sync
2. Configure Environment Variables
Create a .env file in the project root:

Code snippet
OPENAI_API_KEY="your-openai-api-key-here"
JWT_SECRET_KEY="super-secret-jwt-key-change-in-production"
DATABASE_URL="sqlite:///./data/support_agent.db"
3. Initialize the Database
Bash
python -m app.init_db
4. Run the Development Server
Bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Access the interactive Swagger UI at http://localhost:8000/docs.

🐳 Running with Docker
To containerize and run the application using Docker Compose:

Bash
# Build and start containers in detached mode
docker compose up --build -d

# Initialize database inside the container
docker compose exec support-agent python -m app.init_db
🧪 Running Tests
Execute the comprehensive test suite using pytest via uv:

Bash
uv run pytest -v
