"""Thin HTTP handlers: parse the request, call the use case, shape the response."""

import logging
import time

from fastapi import APIRouter, Depends, Query, Request
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.application.analyze import AnalyzeCode
from app.config import Settings, get_settings
from app.domain.models import AnalysisRequest, AnalysisResult, AnalysisType
from app.infrastructure.samples import SampleStore

from .dependencies import get_analyze, get_rate_limiter, get_samples
from .guards import RateLimiter
from .problems import PROBLEM_RESPONSE

logger = logging.getLogger("app.analyze")
router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "model": settings.gemini_model, "llm_mode": settings.llm_mode}


@router.post(
    "/analyze",
    response_model=AnalysisResult,
    responses={code: PROBLEM_RESPONSE for code in (400, 413, 422, 429, 502, 503, 504)},
)
def analyze(
    body: AnalysisRequest,
    request: Request,
    use_case: AnalyzeCode = Depends(get_analyze),
    limiter: RateLimiter = Depends(get_rate_limiter),
) -> AnalysisResult:
    started = time.monotonic()
    result = use_case.lookup(body)  # size check + cache: free, not rate limited
    if result is None:
        limiter.check(request.client.host if request.client else "unknown")
        result = use_case(body)
    m = result.meta
    # Never log the submitted code or the API key — sizes and counters only.
    logger.info(
        "analyze language=%s type=%s chars=%d cached=%s chunks=%d calls=%d tokens=%d/%d ms=%d",
        m.language,
        m.analysis_type,
        len(body.code),
        m.cached,
        m.chunks,
        m.llm_calls,
        m.tokens.input,
        m.tokens.output,
        (time.monotonic() - started) * 1000,
    )
    return result


@router.get("/samples")
def list_samples(samples: SampleStore = Depends(get_samples)) -> list[dict]:
    return samples.catalog()


@router.get("/samples/{sample_id}", responses={404: PROBLEM_RESPONSE})
def get_sample(
    sample_id: str,
    analysis_type: AnalysisType = Query(AnalysisType.GENERAL),
    samples: SampleStore = Depends(get_samples),
) -> dict:
    sample = samples.get(sample_id)
    if sample is None:
        raise StarletteHTTPException(status_code=404, detail="Unknown sample.")
    stored = samples.stored_result(sample_id, analysis_type)
    return sample | {
        "code": samples.code(sample),
        "result": stored.model_dump(mode="json") if stored else None,
    }
