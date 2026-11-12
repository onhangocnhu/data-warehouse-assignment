#!/usr/bin/env bash
# Start the dashboard, preparing whatever is missing first. Safe to run again: finished steps are skipped.
#
#   bash src/dashboard/run.sh            # prepare, then open http://localhost:8501 (Ctrl+C to stop)
#   bash src/dashboard/run.sh --check    # prepare and check only, do not start the dashboard
#
# Steps: .env -> PostgreSQL in Docker -> Python venv -> ETL (if the Data Mart is empty)
#        -> DSS scores (if dss.delay_risk_score is empty) -> login role dashboard_app -> streamlit.
set -euo pipefail

cd "$(dirname "$0")/../.."                       # repository root
CHECK_ONLY=false
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31mError: %s\033[0m\n' "$*" >&2; exit 1; }

# 1. .env (database settings, git-ignored)
step "Settings (.env)"
if [[ ! -f .env ]]; then
    cp .env.example .env
    fail "created .env from .env.example. Open it, set DB_PASSWORD, then run this script again."
fi
set -a; source .env; set +a
[[ "${DB_PASSWORD:-change_me}" == "change_me" ]] && fail "set DB_PASSWORD in .env (it is still 'change_me')."
echo "ok"

# 2. PostgreSQL 16 in Docker
step "PostgreSQL (Docker)"
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop and try again."
docker compose up -d --wait postgres
psql_q() { docker compose exec -T postgres psql -U "${DB_USER:-dw_admin}" -d "${DB_NAME:-olist_dw}" -tAc "$1"; }

# 3. Python environment
step "Python environment (.venv)"
if [[ ! -x .venv/bin/python ]]; then
    PY=$(command -v python3.12 || command -v python3.13 || command -v python3.11 || command -v python3) \
        || fail "Python 3.11+ not found."
    "$PY" -m venv .venv
fi
if command -v uv >/dev/null; then                 # a venv made by uv has no pip
    uv pip install -q --python .venv/bin/python -r requirements.txt
else
    .venv/bin/python -m pip --version >/dev/null 2>&1 || .venv/bin/python -m ensurepip -q
    .venv/bin/python -m pip install -q -r requirements.txt
fi
.venv/bin/python --version

# 4. ETL: CSV files -> staging -> Data Mart (about 20 s)
step "Data Mart"
facts=$(psql_q "SELECT to_regclass('dm.fact_sales') IS NOT NULL AND EXISTS (SELECT 1 FROM dm.fact_sales)" 2>/dev/null || echo f)
if [[ "$facts" != "t" ]]; then
    echo "Data Mart is empty: running the ETL"
    .venv/bin/python -m src.etl.run_etl --init
fi
echo "dm.fact_sales: $(psql_q 'SELECT COUNT(*) FROM dm.fact_sales') rows (expected 112650)"

# 5. DSS scores (uses the committed src/dss/results/best_config.json)
step "DSS scores"
scores=$(psql_q "SELECT EXISTS (SELECT 1 FROM dss.delay_risk_score)" 2>/dev/null || echo f)
if [[ "$scores" != "t" ]]; then
    echo "No DSS scores yet: running src.dss.score_delay"
    .venv/bin/python -m src.dss.score_delay
    echo "Note: score_delay also rewrites CSV files in src/dss/results/ (only rounding differences)."
    echo "      Undo with: git checkout -- src/dss/results/"
fi
echo "dss.delay_risk_score: $(psql_q 'SELECT COUNT(*) FROM dss.delay_risk_score') rows (expected 18753)"

# 6. Dashboard login: SELECT on dm/meta/dss + INSERT on dss.decision_log only
step "Dashboard login (dashboard_app)"
if ! grep -q '^DASHBOARD_DB_USER=' .env; then
    .venv/bin/python -m src.dashboard.setup_role | grep '^DASHBOARD_DB_' >> .env
    echo "role created, login added to .env"
else
    echo "already in .env"
fi

if $CHECK_ONLY; then
    step "All checks passed. Start the dashboard with: bash src/dashboard/run.sh"
    exit 0
fi

# 7. Dashboard
step "Dashboard on http://localhost:8501 (Ctrl+C to stop)"
# headless: skip Streamlit's first-run e-mail prompt; the browser is opened here instead
(sleep 3; [[ -n "${NO_BROWSER:-}" ]] || open http://localhost:8501 2>/dev/null || xdg-open http://localhost:8501 2>/dev/null || true) &
exec .venv/bin/streamlit run src/dashboard/app.py --server.headless true
