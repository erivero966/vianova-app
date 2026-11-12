"""Contratos JSON de la API (request/response)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


TOP_K_MIN = 1
TOP_K_MAX = 10
QUERY_MAX_CHARS = 2000

QueryText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=QUERY_MAX_CHARS)
]


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"query": "náuseas después de la quimioterapia", "top_k": 3}]
        },
    )

    query: QueryText = Field(description="Consulta en lenguaje natural (no vacía).")
    top_k: int = Field(default=3, ge=TOP_K_MIN, le=TOP_K_MAX, description="Número de fragmentos (1-10).")


class SearchResultItem(BaseModel):
    rank: int
    fragment_id: str
    score: float = Field(description="Similitud coseno = 1 - distance.")
    distance: float = Field(description="Distancia coseno de pgvector (<=>); menor es más parecido.")
    text: str
    document: str
    entity: str | None
    version: str
    section: str | None
    page_start: int | None
    page_end: int | None


class SearchResponse(BaseModel):
    query: str
    model: str
    top_k: int
    results: list[SearchResultItem]


class HealthResponse(BaseModel):
    status: str
    database: str
    model: str
    retrieval: str
    device: str | None = None
    dimension: int | None = None
    embeddings: int | None = None


class ErrorResponse(BaseModel):
    detail: str
