"""Aplicación FastAPI del sistema Vianova."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import Base, engine, SessionLocal
from .models import User, Document, CorpusState
from .rag.corpus import load_directory, current_version
from .rag.index import INDEX
from .routers import auth, care, knowledge, research, admin, privacy
from .security import hash_password


def init_db() -> None:
    config.check_production()
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if not db.query(CorpusState).first():
            db.add(CorpusState(version="v1.0"))
            db.commit()
        for email, pw, role, name, code in [
            (config.ADMIN_EMAIL, config.ADMIN_PASSWORD, "curador", "Curador del corpus", "CUR-001"),
            (config.RESEARCHER_EMAIL, config.RESEARCHER_PASSWORD, "investigador", "Investigador", "INV-001"),
            (config.SYSADMIN_EMAIL, config.SYSADMIN_PASSWORD, "admin", "Administrador del sistema", "ADM-002"),
        ]:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(code=code, email=email, full_name=name, password_hash=hash_password(pw), role=role))
        db.commit()
        if db.query(Document).count() == 0 and config.CORPUS_DIR.exists():
            load_directory(db, config.CORPUS_DIR)
        INDEX.build(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Vianova API", version="1.0.0", lifespan=lifespan,
              description="Aplicación móvil de recomendaciones con RAG para cuidadores familiares de pacientes con cáncer")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
    if not request.url.path.startswith(("/docs", "/redoc")):
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                                   "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
                                                   "manifest-src 'self'; worker-src 'self'")
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


for r in (auth.router, care.router, knowledge.router, research.router, admin.router, privacy.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    db = SessionLocal()
    try:
        return {"status": "ok", "ambiente": config.APP_ENV, "corpus_version": current_version(db), "indexed_chunks": len(INDEX.chunks),
                "llm_provider": config.LLM_PROVIDER, "tau": config.RAG_TAU}
    finally:
        db.close()


# ---------------------------------------------------------------- aplicación web compilada
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "No encontrado"}, status_code=404)
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
