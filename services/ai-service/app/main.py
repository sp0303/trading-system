import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import httpx
from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("hedge_fund_ai_service")

# =============================================================================
# CONFIG
# =============================================================================
app = FastAPI(title="Nifty 50 AI Service (Hedge Fund Grade)")

# --- Monitoring ---
AI_REQUEST_COUNT = Counter("ai_service_requests_total", "Total requests", ["status", "source"])
AI_REQUEST_LATENCY = Histogram("ai_service_request_latency_seconds", "Request latency", ["symbol"])

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")
# Default to host.docker.internal for Docker-to-Host communication
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")

REQUEST_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
RETRY_ATTEMPTS = int(os.getenv("OLLAMA_RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("OLLAMA_RETRY_BACKOFF_SECONDS", "1.25"))

MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "16000"))
MAX_FIELD_CHARS = int(os.getenv("MAX_FIELD_CHARS", "3000"))
MAX_NEWS_ITEMS = int(os.getenv("MAX_NEWS_ITEMS", "5"))
MAX_STRATEGY_ITEMS = int(os.getenv("MAX_STRATEGY_ITEMS", "8"))

ALLOWED_DECISIONS = {"BUY", "SELL", "HOLD"}
ALLOWED_CONVICTIONS = {"High", "Medium", "Low"}

# =============================================================================
# SCHEMAS
# =============================================================================
class AnalyzeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=30)
    context: Dict[str, Any] = Field(default_factory=dict)
    debug: bool = False


class ModelRationale(BaseModel):
    price_action: str = ""
    fundamental_flow: str = ""
    strategy_regime: str = ""
    risk_management: str = ""


class ModelKeyLevels(BaseModel):
    support: List[str] = Field(default_factory=list)
    resistance: List[str] = Field(default_factory=list)


class ModelOutput(BaseModel):
    decision: str = "HOLD"
    conviction: str = "Low"
    confidence_score: int = Field(default=50, ge=0, le=100)
    thesis: str = ""
    rationale: ModelRationale = Field(default_factory=ModelRationale)
    key_levels: ModelKeyLevels = Field(default_factory=ModelKeyLevels)
    catalysts: List[str] = Field(default_factory=list)
    invalidations: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


# =============================================================================
# GENERIC HELPERS
# =============================================================================
def model_dump_safe(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def clamp_text(value: Any, limit: int = MAX_FIELD_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            text = str(value)
    else:
        text = str(value)

    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def strip_code_fences(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"^```(?:json|markdown|md)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None

    cleaned = strip_code_fences(text)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Try to rescue the first JSON object in messy model output
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        candidate = match.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def normalize_decision(value: Any) -> str:
    v = str(value or "").upper().strip()
    return v if v in ALLOWED_DECISIONS else "HOLD"


def normalize_conviction(value: Any) -> str:
    v = str(value or "").capitalize().strip()
    return v if v in ALLOWED_CONVICTIONS else "Low"


def safe_int(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(value)))
    except Exception:
        return default


def listify(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


# =============================================================================
# CONTEXT COMPRESSION LAYER
# =============================================================================
def normalize_news_item(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        title = clamp_text(item.get("title") or item.get("headline") or "")
        summary = clamp_text(item.get("summary") or item.get("description") or "")
        source = clamp_text(item.get("source") or "")
        sentiment = clamp_text(item.get("sentiment_label") or item.get("sentiment") or "")
        relevance = item.get("relevance_score", item.get("score", 0))
        published = clamp_text(item.get("published") or item.get("date") or "")
        return {
            "title": title,
            "summary": summary,
            "source": source,
            "sentiment": sentiment,
            "relevance": relevance,
            "published": published,
        }

    text = clamp_text(item)
    return {
        "title": text[:220],
        "summary": "",
        "source": "",
        "sentiment": "",
        "relevance": 0,
        "published": "",
    }


def choose_top_news(news_raw: Any) -> List[str]:
    items = listify(news_raw)
    normalized = [normalize_news_item(x) for x in items]

    def sort_key(x: Dict[str, Any]) -> tuple:
        relevance = x.get("relevance", 0)
        try:
            relevance = float(relevance)
        except Exception:
            relevance = 0.0
        sentiment_bonus = 0.0
        sent = (x.get("sentiment") or "").lower()
        if "bull" in sent:
            sentiment_bonus = 0.25
        elif "bear" in sent:
            sentiment_bonus = -0.10
        return (relevance + sentiment_bonus, len(x.get("title", "")))

    normalized.sort(key=sort_key, reverse=True)
    top = normalized[:MAX_NEWS_ITEMS]

    lines = []
    for i, n in enumerate(top, start=1):
        parts = [n["title"]]
        if n["sentiment"]:
            parts.append(f"({n['sentiment']})")
        if n["source"]:
            parts.append(f"- {n['source']}")
        if n["published"]:
            parts.append(f"[{n['published']}]")
        if n["summary"]:
            parts.append(f"| {n['summary']}")
        line = " ".join(parts)
        lines.append(f"{i}) {normalize_whitespace(line)}")

    return lines


def choose_strategy_summary(strategy_raw: Any) -> str:
    items = listify(strategy_raw)

    # Accept already-compressed string directly
    if len(items) == 1 and isinstance(items[0], str):
        return clamp_text(items[0], MAX_FIELD_CHARS)

    lines = []
    for item in items[:MAX_STRATEGY_ITEMS]:
        if isinstance(item, dict):
            name = clamp_text(item.get("name") or item.get("strategy") or item.get("strategy_name") or "Strategy")
            signal = clamp_text(item.get("signal") or item.get("decision") or item.get("action") or "")
            score = item.get("score", item.get("strength", item.get("confidence", "")))
            reason = clamp_text(item.get("reason") or item.get("rationale") or item.get("notes") or "")
            chunks = [name]
            if signal:
                chunks.append(f"={signal}")
            if score != "":
                chunks.append(f"[score: {score}]")
            if reason:
                chunks.append(f"- {reason}")
            lines.append(" ".join(chunks))
        else:
            lines.append(clamp_text(item))

    return "\n".join(lines)[:MAX_FIELD_CHARS]


def choose_institutional_summary(institutional_raw: Any) -> str:
    if isinstance(institutional_raw, str):
        return clamp_text(institutional_raw)

    if isinstance(institutional_raw, dict):
        parts = []
        for k in ["delivery", "fii", "dii", "breadth", "flow", "signal", "score", "sentiment"]:
            if k in institutional_raw:
                parts.append(f"{k}: {clamp_text(institutional_raw.get(k))}")
        if parts:
            return "\n".join(parts)
        return clamp_text(institutional_raw)

    return clamp_text(institutional_raw)


def choose_fundamentals_summary(fundamentals_raw: Any) -> str:
    if isinstance(fundamentals_raw, str):
        return clamp_text(fundamentals_raw)

    if isinstance(fundamentals_raw, dict):
        preferred_keys = [
            "summary", "business_summary", "valuation", "growth", "profitability",
            "moat", "sector", "risk", "margin", "debt", "promoter", "quality"
        ]
        parts = []
        for k in preferred_keys:
            if k in fundamentals_raw and fundamentals_raw.get(k) not in (None, "", [], {}):
                parts.append(f"{k}: {clamp_text(fundamentals_raw.get(k))}")
        if parts:
            return "\n".join(parts)
        return clamp_text(fundamentals_raw)

    return clamp_text(fundamentals_raw)


def choose_regime_summary(regime_raw: Any) -> str:
    if isinstance(regime_raw, str):
        return clamp_text(regime_raw)
    return clamp_text(regime_raw)


def choose_technicals_summary(technicals_raw: Any) -> str:
    if isinstance(technicals_raw, str):
        return clamp_text(technicals_raw)

    if isinstance(technicals_raw, dict):
        preferred = [
            "trend", "vwap", "support", "resistance", "breakout", "breakdown",
            "volume", "momentum", "atr", "rsi", "ema", "sma", "pattern"
        ]
        parts = []
        for k in preferred:
            if k in technicals_safe(technicals_raw):
                parts.append(f"{k}: {clamp_text(technicals_raw.get(k))}")
        if parts:
            return "\n".join(parts)
        return clamp_text(technicals_raw)

    return clamp_text(technicals_raw)


def technicals_safe(data: Dict[str, Any]) -> Dict[str, Any]:
    # tolerant alias wrapper in case callers use different field names
    return data or {}


def compress_context(context: Dict[str, Any]) -> Dict[str, str]:
    return {
        "fundamentals": choose_fundamentals_summary(context.get("fundamentals", "")),
        "news": "\n".join(choose_top_news(context.get("news", [])))[:MAX_CONTEXT_CHARS],
        "strategy_results": choose_strategy_summary(context.get("strategy_results", "")),
        "institutional": choose_institutional_summary(context.get("institutional", "")),
        "regime": choose_regime_summary(context.get("regime", "")),
        "technicals_1h": choose_technicals_summary(context.get("technicals_1h", "")),
    }


def context_to_single_text(context: Dict[str, str]) -> str:
    merged = (
        f"Fundamentals:\n{context.get('fundamentals','')}\n\n"
        f"News:\n{context.get('news','')}\n\n"
        f"Strategy Signals:\n{context.get('strategy_results','')}\n\n"
        f"Institutional Flow:\n{context.get('institutional','')}\n\n"
        f"Market Regime:\n{context.get('regime','')}\n\n"
        f"Intraday Technicals (1H):\n{context.get('technicals_1h','')}"
    )
    return merged[:MAX_CONTEXT_CHARS]


# =============================================================================
# PROMPT ENGINE
# =============================================================================
def build_prompt(symbol: str, context: Dict[str, str]) -> str:
    return f"""
You are a high-precision institutional trading decision engine.

Mission:
- Produce a conservative, risk-aware, evidence-based decision.
- Default bias is HOLD when evidence is mixed, weak, incomplete, or conflicting.
- Do not speculate.
- Do not invent prices, indicators, events, or levels not present in the input.
- Use only the supplied context.
- Do not explain your process outside the requested JSON.

Symbol: {symbol}

====================
CLEANED INPUT
====================

Fundamentals:
{context.get("fundamentals", "")}

News:
{context.get("news", "")}

Strategy Signals:
{context.get("strategy_results", "")}

Institutional Flow:
{context.get("institutional", "")}

Market Regime:
{context.get("regime", "")}

Intraday Technicals (1H):
{context.get("technicals_1h", "")}

====================
DECISION RULES
====================
1. Return BUY or SELL only when technicals, institutional flow, strategy alignment, and news all support the thesis.
2. If signals conflict, return HOLD.
3. If data is missing or weak, return HOLD.
4. If the move looks like noise, liquidity chase, or retail speculation, return HOLD.
5. Conviction should be High only with strong multi-factor alignment.
6. Confidence score must reflect uncertainty; be conservative.

CONSISTENCY RULE:
- Decision MUST match rationale
- If rationale is bearish → cannot return BUY
- If rationale is mixed → MUST return HOLD

====================
OUTPUT SCHEMA
====================
Return ONLY valid JSON with this exact schema:

{{
  "decision": "BUY|SELL|HOLD",
  "conviction": "High|Medium|Low",
  "confidence_score": 0-100,
  "thesis": "one concise sentence",
  "rationale": {{
    "price_action": "1-3 sentences",
    "fundamental_flow": "1-3 sentences",
    "strategy_regime": "1-3 sentences",
    "risk_management": "1-3 sentences"
  }},
  "key_levels": {{
    "support": ["level or zone strings"],
    "resistance": ["level or zone strings"]
  }},
  "catalysts": ["top catalysts"],
  "invalidations": ["thesis breakers"],
  "notes": ["additional concise notes"]
}}

Important:
- Output JSON only.
- No markdown.
- No code fences.
- No extra text.
- No hallucinated precision.
""".strip()


# =============================================================================
# FALLBACK ENGINE
# =============================================================================
def fallback_analysis(symbol: str, context: Dict[str, str]) -> ModelOutput:
    combined = " ".join(context.values()).lower()

    bullish_terms = [
        "buy", "bullish", "accumulation", "breakout", "support held",
        "strong", "positive", "upgrade", "beat", "beats", "surge",
        "higher highs", "volume pickup", "institutional buying",
        "delivery", "outperform", "momentum"
    ]
    bearish_terms = [
        "sell", "bearish", "distribution", "breakdown", "resistance held",
        "weak", "negative", "downgrade", "miss", "misses", "drop",
        "lower lows", "selling pressure", "institutional selling",
        "underperform", "failure", "rejection"
    ]

    score = 0
    for term in bullish_terms:
        if term in combined:
            score += 1
    for term in bearish_terms:
        if term in combined:
            score -= 1

    # Simple regime / risk adjustments
    if "bull" in combined and "breakdown" not in combined:
        score += 1
    if "bear" in combined and "breakout" not in combined:
        score -= 1
    if "mixed" in combined or "unclear" in combined:
        score -= 1

    if score >= 5:
        decision = "BUY"
        conviction = "High"
        confidence = 78
    elif score <= -5:
        decision = "SELL"
        conviction = "High"
        confidence = 78
    elif score >= 2:
        decision = "BUY"
        conviction = "Low"
        confidence = 58
    elif score <= -2:
        decision = "SELL"
        conviction = "Low"
        confidence = 58
    else:
        decision = "HOLD"
        conviction = "Medium"
        confidence = 50

    rationale = ModelRationale(
        price_action="Fallback engine sees no sufficiently strong intraday confirmation to override uncertainty.",
        fundamental_flow="Fallback engine finds no decisive fundamental-flow alignment from the compressed context.",
        strategy_regime="Fallback engine is intentionally conservative unless multiple independent signals align.",
        risk_management="Use the nearest technical support and resistance from your technical feed; reduce size if regime is not aligned."
    )

    return ModelOutput(
        decision=decision,
        conviction=conviction,
        confidence_score=confidence,
        thesis=f"Fallback decision for {symbol} based on deterministic signal compression.",
        rationale=rationale,
        key_levels=ModelKeyLevels(support=[], resistance=[]),
        catalysts=[],
        invalidations=[
            "If price loses the key support from technicals, the thesis weakens immediately.",
            "If institutional flow turns opposite to the thesis, conviction should be reduced."
        ],
        notes=[
            "Fallback was used because the model output was missing, invalid, slow, or unavailable.",
            "This is safe output, not alpha-generating output."
        ]
    )


def validate_decision_consistency(result: ModelOutput) -> ModelOutput:
    """
    MANDATORY structural check: ensures categorical decision matches verbal rationale.
    """
    text = (
        result.rationale.price_action.lower() + " " +
        result.rationale.fundamental_flow.lower() + " " +
        result.rationale.strategy_regime.lower()
    )

    bearish_signals = ["bearish", "downside", "weak", "breakdown", "lower", "sell", "rejection", "failure"]
    bullish_signals = ["bullish", "upside", "strong", "breakout", "higher", "buy", "accumulation", "support held"]

    bearish_score = sum(1 for w in bearish_signals if w in text)
    bullish_score = sum(1 for w in bullish_signals if w in text)

    # 🚨 Conflict detection
    if result.decision == "BUY" and bearish_score > bullish_score:
        result.decision = "HOLD"
        result.conviction = "Low"
        result.notes.append("Decision corrected: bearish rationale mismatch detected by Validator.")

    if result.decision == "SELL" and bullish_score > bearish_score:
        result.decision = "HOLD"
        result.conviction = "Low"
        result.notes.append("Decision corrected: bullish rationale mismatch detected by Validator.")

    return result


# =============================================================================
# OLLAMA INTEGRATION
# =============================================================================
async def ollama_health_check() -> Dict[str, Any]:
    url = f"{OLLAMA_BASE_URL}/api/tags"
    timeout = httpx.Timeout(5.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    models = data.get("models", [])
    ready = any(m.get("name") == MODEL or m.get("model") == MODEL for m in models)
    return {
        "available": True,
        "model_ready": ready,
        "models": models,
    }


async def call_ollama_chat(prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict financial decision engine. "
                    "Return only valid JSON matching the requested schema. "
                    "No markdown. No code fences. No commentary."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 700,
        },
    }

    timeout_val = REQUEST_TIMEOUT_SECONDS
    last_error: Optional[Exception] = None

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            logger.warning(f"Ollama attempt {attempt}/{RETRY_ATTEMPTS} failed ({error_type}): {e}")
            if attempt < RETRY_ATTEMPTS:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise last_error if last_error else RuntimeError("Unknown Ollama failure")


def validate_model_output(raw: str) -> ModelOutput:
    parsed = extract_json_object(raw)
    if not parsed:
        raise ValueError("Model output was not valid JSON")

    parsed["decision"] = normalize_decision(parsed.get("decision"))
    parsed["conviction"] = normalize_conviction(parsed.get("conviction"))
    parsed["confidence_score"] = safe_int(parsed.get("confidence_score"), default=50)

    # Normalize nested objects
    rationale = parsed.get("rationale", {}) or {}
    key_levels = parsed.get("key_levels", {}) or {}

    if not isinstance(rationale, dict):
        rationale = {}
    if not isinstance(key_levels, dict):
        key_levels = {}

    parsed["rationale"] = {
        "price_action": clamp_text(rationale.get("price_action", "")),
        "fundamental_flow": clamp_text(rationale.get("fundamental_flow", "")),
        "strategy_regime": clamp_text(rationale.get("strategy_regime", "")),
        "risk_management": clamp_text(rationale.get("risk_management", "")),
    }
    parsed["key_levels"] = {
        "support": [clamp_text(x) for x in listify(key_levels.get("support", []))[:5]],
        "resistance": [clamp_text(x) for x in listify(key_levels.get("resistance", []))[:5]],
    }
    parsed["catalysts"] = [clamp_text(x) for x in listify(parsed.get("catalysts", []))[:8]]
    parsed["invalidations"] = [clamp_text(x) for x in listify(parsed.get("invalidations", []))[:8]]
    parsed["notes"] = [clamp_text(x) for x in listify(parsed.get("notes", []))[:8]]
    parsed["thesis"] = clamp_text(parsed.get("thesis", ""), 500)

    return ModelOutput(**parsed)


def render_markdown(result: ModelOutput) -> str:
    md = []
    md.append(f"### DECISION: {result.decision}")
    md.append(f"**CONVICTION**: {result.conviction}")
    md.append(f"**CONFIDENCE SCORE**: {result.confidence_score}/100")
    md.append("")
    md.append(f"**THESIS**: {result.thesis}")
    md.append("")
    md.append("**RATIONALE**:")
    md.append(f"- **Price Action (1H)**: {result.rationale.price_action}")
    md.append(f"- **Fundamental & Flow Alignment**: {result.rationale.fundamental_flow}")
    md.append(f"- **Strategy & Regime Context**: {result.rationale.strategy_regime}")
    md.append(f"- **Risk Management**: {result.rationale.risk_management}")

    if result.key_levels.support or result.key_levels.resistance:
        md.append("")
        md.append("**KEY LEVELS**:")
        if result.key_levels.support:
            md.append(f"- Support: {', '.join(result.key_levels.support)}")
        if result.key_levels.resistance:
            md.append(f"- Resistance: {', '.join(result.key_levels.resistance)}")

    if result.catalysts:
        md.append("")
        md.append("**CATALYSTS**:")
        for c in result.catalysts[:5]:
            md.append(f"- {c}")

    if result.invalidations:
        md.append("")
        md.append("**INVALIDATIONS**:")
        for i in result.invalidations[:5]:
            md.append(f"- {i}")

    if result.notes:
        md.append("")
        md.append("**NOTES**:")
        for n in result.notes[:5]:
            md.append(f"- {n}")

    return "\n".join(md)


# =============================================================================
# ROUTES
# =============================================================================
@app.get("/health")
async def health():
    try:
        info = await ollama_health_check()
        return {
            "status": "ok" if info["available"] and info["model_ready"] else "degraded",
            "service": "ai-service",
            "model": MODEL,
            "ollama_available": info["available"],
            "model_ready": info["model_ready"],
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "service": "ai-service",
            "model": MODEL,
            "ollama_available": False,
            "model_ready": False,
            "message": str(e),
        }


@app.post("/analyze")
async def analyze_stock(payload: AnalyzeRequest = Body(...)):
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Symbol missing from request")

    compressed_context = compress_context(payload.context)
    prompt = build_prompt(symbol, compressed_context)

    start = time.perf_counter()

    try:
        logger.info(f"Starting analysis for {symbol}")

        raw = await call_ollama_chat(prompt)
        result = validate_model_output(raw)
        
        AI_REQUEST_COUNT.labels(status="success", source="ollama").inc()
        
        # 🔥 FIX: ADD DECISION VALIDATOR (MANDATORY)
        result = validate_decision_consistency(result)

        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "model": MODEL,
                "source": "ollama-gemma",
                "is_fallback": False,
                "latency_ms": latency_ms,
                "analysis": render_markdown(result),
                "structured": model_dump_safe(result),
                "context_summary": compressed_context,
            },
        }

    except (ValueError, ValidationError) as e:
        logger.warning(f"Model output invalid for {symbol}: {e}")
        fallback = fallback_analysis(symbol, compressed_context)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "status": "success",
            "data": {
                "symbol": symbol,
                "model": MODEL,
                "source": "rule-based-fallback",
                "is_fallback": True,
                "latency_ms": latency_ms,
                "analysis": render_markdown(fallback),
                "structured": model_dump_safe(fallback),
                "error_detail": "Model output invalid; fallback used.",
                "context_summary": compressed_context,
            },
        }

    except Exception as e:
        logger.error(f"Error during analysis for {symbol}: {e}")
        fallback = fallback_analysis(symbol, compressed_context)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        return {
            "status": "degraded",
            "data": {
                "symbol": symbol,
                "model": MODEL,
                "source": "rule-based-fallback",
                "is_fallback": True,
                "latency_ms": latency_ms,
                "analysis": render_markdown(fallback),
                "structured": model_dump_safe(fallback),
                "error_detail": str(e),
                "context_summary": compressed_context,
            },
        }


@app.post("/analyze/raw")
async def analyze_raw(payload: AnalyzeRequest = Body(...)):
    symbol = payload.symbol.strip().upper()
    compressed_context = compress_context(payload.context)
    prompt = build_prompt(symbol, compressed_context)

    raw = await call_ollama_chat(prompt)
    parsed = extract_json_object(raw)
    
    # Apply normalization and validation even to raw debug output if possible
    try:
        validated = validate_model_output(raw)
        validated = validate_decision_consistency(validated)
        parsed_validated = model_dump_safe(validated)
    except:
        parsed_validated = parsed

    return {
        "status": "success",
        "symbol": symbol,
        "prompt": prompt,
        "raw_output": raw,
        "parsed": parsed,
        "context_summary": compressed_context,
    }


@app.post("/debug/prompt")
async def debug_prompt(payload: AnalyzeRequest = Body(...)):
    symbol = payload.symbol.strip().upper()
    compressed_context = compress_context(payload.context)
    prompt = build_prompt(symbol, compressed_context)
    return {
        "status": "success",
        "symbol": symbol,
        "compressed_context": compressed_context,
        "prompt": prompt,
    }


@app.get("/model")
async def model_info():
    return {
        "status": "success",
        "model": MODEL,
        "ollama_base_url": OLLAMA_BASE_URL,
        "timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "retry_attempts": RETRY_ATTEMPTS,
        "max_context_chars": MAX_CONTEXT_CHARS,
    }


@app.get("/version")
async def version():
    return {
        "service": "ai-service",
        "version": "hedge-fund-grade-v1",
        "decision_policy": "hold-first conservative decisioning",
    }


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7011, reload=False)