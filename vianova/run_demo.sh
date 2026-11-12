#!/usr/bin/env bash
# Prototipo integrado: PostgreSQL+pgvector -> rag-engine :8001 -> Ollama :11434 (qwen2.5:7b) -> backend Vianova :8000.
# Uso:  ./run_demo.sh          (app en http://localhost:8000; el backend sirve frontend/dist)
#       ./run_demo.sh --vite   (además el frontend de desarrollo en http://localhost:5173)
# Reutiliza lo que ya esté levantado. Ollama: si su API no responde, lo inicia (servicio systemd si existe; si no,
# `ollama serve` en segundo plano). Nunca ejecuta `ollama run` ni descarga modelos: qwen2.5:7b se carga en memoria
# con la primera consulta real (POST /api/chat).
# Ctrl+C detiene el rag-engine, el backend y Vite si este script los inició. PostgreSQL (Docker) y Ollama siguen activos.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAG="$ROOT/rag-engine"
BACKEND="$ROOT/vianova/backend"
FRONTEND="$ROOT/vianova/frontend"
export RAG_API_URL="${RAG_API_URL:-http://127.0.0.1:8001}"
export OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
OLLAMA_LOG="${OLLAMA_LOG:-/tmp/vianova-ollama.log}"
OLLAMA_WAIT_S="${OLLAMA_WAIT_S:-30}"
OLLAMA_HOSTPORT="${OLLAMA_URL#*://}"; OLLAMA_HOSTPORT="${OLLAMA_HOSTPORT%%/*}"
OLLAMA_PORT="${OLLAMA_HOSTPORT##*:}"

pids=()
cleanup() { [ ${#pids[@]} -gt 0 ] && kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

ok()   { echo "[OK] $*"; }
info() { echo "[INFO] $*"; }
fail() { echo "[ERROR] $*" >&2; exit 1; }
port_busy() { ss -ltn 2>/dev/null | grep -q ":$1 "; }
wait_for() {  # wait_for URL SEGUNDOS: reintentos cortos (0,5 s) hasta que la URL responda
  local tries=$(( $2 * 2 ))
  for _ in $(seq 1 "$tries"); do curl -fs "$1" >/dev/null 2>&1 && return 0; sleep 0.5; done
  return 1
}

# ---------------------------------------------------------------- 1. PostgreSQL + pgvector
(cd "$RAG" && docker compose up -d --wait >/dev/null 2>&1) || fail "PostgreSQL no pudo iniciarse (cd $RAG && docker compose up -d)."
ok "PostgreSQL disponible"

# ---------------------------------------------------------------- 2. rag-engine :8001
if ! port_busy 8001; then
  info "Iniciando RAG Engine (BGE-M3, HF_HUB_OFFLINE=1)..."
  (cd "$RAG" && HF_HUB_OFFLINE=1 .venv/bin/uvicorn src.api.app:app --host 0.0.0.0 --port 8001) & pids+=($!)
fi
wait_for http://127.0.0.1:8001/health 120 || fail "RAG Engine no respondió en :8001."
ok "RAG Engine disponible en :8001"

# ---------------------------------------------------------------- 3. Ollama :11434
ollama_up() { curl -fsS "$OLLAMA_URL/api/tags" >/dev/null 2>&1; }
if ollama_up; then
  ok "Ollama disponible en :$OLLAMA_PORT (se reutiliza el servicio existente)"
else
  command -v ollama >/dev/null 2>&1 || fail "Ollama no está instalado (no se encontró el comando 'ollama')."
  info "Ollama no estaba iniciado. Levantando servicio..."
  if [ "$OLLAMA_PORT" = "11434" ] && systemctl cat ollama.service >/dev/null 2>&1; then
    # Instalación oficial en Linux: el servicio corre como usuario 'ollama' y sus modelos están en
    # /usr/share/ollama. Un `ollama serve` del usuario actual no vería esos modelos, por eso se usa systemd.
    OLLAMA_LOG="journalctl -u ollama"
    systemctl is-active --quiet ollama.service || systemctl start ollama.service \
      || fail "No se pudo iniciar el servicio de Ollama. Ejecuta: sudo systemctl start ollama"
  else
    OLLAMA_HOST="$OLLAMA_HOSTPORT" setsid nohup ollama serve >"$OLLAMA_LOG" 2>&1 < /dev/null &
  fi
  wait_for "$OLLAMA_URL/api/tags" "$OLLAMA_WAIT_S" || { printf '[ERROR] Ollama no pudo iniciarse.\nRevisa: %s\n' "$OLLAMA_LOG" >&2; exit 1; }
  ok "Ollama disponible en :$OLLAMA_PORT"
fi

# El modelo debe estar instalado; no se descarga ni se precarga (lo carga la primera consulta).
curl -fsS "$OLLAMA_URL/api/tags" 2>/dev/null | python3 -c '
import json, sys
names = {m.get("name") for m in json.load(sys.stdin).get("models", [])}
sys.exit(0 if sys.argv[1] in names else 1)' "$OLLAMA_MODEL" \
  || { printf '[ERROR] %s no está instalado.\nEjecuta manualmente:\nollama pull %s\n' "$OLLAMA_MODEL" "$OLLAMA_MODEL" >&2; exit 1; }
ok "$OLLAMA_MODEL instalado"

# ---------------------------------------------------------------- 4. Backend Vianova :8000
if port_busy 8000; then
  info "El puerto 8000 ya está en uso; se reutiliza ese backend (debe tener RAG_API_URL=$RAG_API_URL)."
else
  (cd "$BACKEND" && .venv/bin/uvicorn app.main:app --port 8000) & pids+=($!)
fi
wait_for http://127.0.0.1:8000/api/health 60 || fail "El backend no respondió en :8000."
ok "Backend Vianova disponible en :8000"

# ---------------------------------------------------------------- 5. Frontend
if [ "${1:-}" = "--vite" ]; then
  if port_busy 5173; then
    info "El puerto 5173 ya está en uso; se reutiliza ese frontend."
  else
    (cd "$FRONTEND" && npx vite --port 5173 --strictPort) & pids+=($!)
  fi
  wait_for http://localhost:5173 60 || fail "El frontend no respondió en :5173."
  ok "Frontend Vite disponible en :5173"
  echo "Abra http://localhost:5173/#/consultar  (demo@vianova.local / Demo2026!)"
else
  ok "Frontend servido por el backend (frontend/dist)"
  echo "Abra http://localhost:8000/#/consultar  (demo@vianova.local / Demo2026!)"
fi
echo "La primera consulta carga $OLLAMA_MODEL en memoria (puede tardar unos segundos más). Ctrl+C para detener."
wait
