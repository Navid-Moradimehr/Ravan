from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.common.query_plan import build_query_plan
from services.common.retrieval import build_retrieval_catalog, search_retrieval_corpus
from services.common.semantic_model import load_semantic_model
from services.common.sql_compiler import compile_readonly_sql
from services.historian.client import query_sql_readonly


router = APIRouter(tags=["search"])


class PlanRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=100, ge=1, le=1000)


class SemanticQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    limit: int = Field(default=100, ge=1, le=1000)
    execute: bool = True


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    table: str = "industrial_events"
    limit: int = Field(default=25, ge=1, le=1000)
    max_results: int = Field(default=5, ge=1, le=25)
    asset_config: str = "config/assets.yaml"
    use_embeddings: bool = True


@router.get("/api/v1/search/catalog")
async def get_search_catalog() -> dict[str, Any]:
    return build_retrieval_catalog(asset_config=Path("config/assets.yaml"))


@router.post("/api/v1/search/plan")
async def post_plan(req: PlanRequest) -> dict[str, Any]:
    semantic_model = load_semantic_model()
    plan = build_query_plan(req.query, model=semantic_model, limit=req.limit)
    try:
        compiled = compile_readonly_sql(plan, model=semantic_model)
    except Exception as exc:
        return {
            "query": req.query,
            "plan": plan.to_dict(),
            "compile_error": str(exc),
        }
    return {
        "query": req.query,
        "plan": plan.to_dict(),
        "sql": compiled.sql,
        "params": list(compiled.params),
        "warnings": list(compiled.warnings),
    }


@router.post("/api/v1/search/semantic")
async def post_semantic(req: SemanticQueryRequest) -> dict[str, Any]:
    semantic_model = load_semantic_model()
    plan = build_query_plan(req.query, model=semantic_model, limit=req.limit)
    try:
        compiled = compile_readonly_sql(plan, model=semantic_model)
    except Exception as exc:
        return {
            "query": req.query,
            "plan": plan.to_dict(),
            "compile_error": str(exc),
            "rows": [],
            "row_count": 0,
        }
    rows: list[dict[str, Any]] = []
    execution_error: str | None = None
    if req.execute:
        try:
            rows = query_sql_readonly(compiled.sql, compiled.params)
        except Exception as exc:
            execution_error = str(exc)
    return {
        "query": req.query,
        "plan": plan.to_dict(),
        "sql": compiled.sql,
        "params": list(compiled.params),
        "warnings": list(compiled.warnings),
        "rows": rows,
        "row_count": len(rows),
        "execution_error": execution_error,
    }


@router.post("/api/v1/search/hybrid")
async def post_hybrid(req: HybridSearchRequest) -> dict[str, Any]:
    try:
        return search_retrieval_corpus(
            req.query,
            table=req.table,
            limit=req.limit,
            asset_config=Path(req.asset_config),
            max_results=req.max_results,
            use_embeddings=req.use_embeddings,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
