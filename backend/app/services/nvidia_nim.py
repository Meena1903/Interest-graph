"""
services/nvidia_nim.py
======================
NVIDIA NIM API integration.

THIS IS THE ONLY MODULE WHERE LLMs ARE CALLED.

LLM is used EXCLUSIVELY for:
  1. NLP interest-tag extraction from post text
     → Input: raw post content
     → Output: list of interest names (structured via Pydantic)
  2. Optional: semantic embedding generation for interest vectors

ALL ranking math, scoring, decay, MMR, trust propagation = pure Python.
This module NEVER makes ranking decisions. It only extracts structured
metadata from unstructured text.
"""

import json
import logging
import time
from typing import Dict, List, Optional

import httpx
from langfuse import Langfuse

from app.core.config import settings
from app.models.entities import Interest

logger = logging.getLogger(__name__)

# Initialize Langfuse client for LLM monitoring
langfuse_client = None
if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
    try:
        langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_BASE_URL
        )
        logger.info("[NvidiaNim] Langfuse client initialized successfully.")
    except Exception as e:
        logger.error("[NvidiaNim] Failed to initialize Langfuse: %s", e)
else:
    logger.warning("[NvidiaNim] Langfuse credentials missing. LLM tracing disabled.")

logger.info(
    "[NvidiaNim] Module loaded | base_url=%s | llm_model=%s | embed_model=%s",
    settings.NVIDIA_BASE_URL,
    settings.NVIDIA_LLM_MODEL,
    settings.NVIDIA_EMBED_MODEL,
)


# ---------------------------------------------------------------------------
# HTTP client factory
# ---------------------------------------------------------------------------

def _get_headers() -> Dict[str, str]:
    """Return auth headers for NVIDIA NIM API."""
    return {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Interest tag extraction via LLM (the ONLY LLM touchpoint for content)
# ---------------------------------------------------------------------------

async def extract_interest_tags(
    content: str,
    available_interests: List[Interest],
    post_id: Optional[int] = None,
) -> Dict:
    """
    Call NVIDIA NIM LLM to extract interest tags from post content.

    This is the ONLY place LLMs are used in the ranking/content pipeline.
    The output is purely structural metadata (interest names → IDs).
    No ranking decisions are made here.

    Model: meta/llama-3.1-70b-instruct (via NVIDIA NIM API)

    Prompt strategy:
        - System: strict instructions to return only JSON list of interest names
        - User: post content + taxonomy list
        - Temperature: 0.1 (near-deterministic for structured extraction)

    Args:
        content:             Raw post text to tag
        available_interests: List of Interest ORM objects (taxonomy)
        post_id:             Optional post ID for logging

    Returns:
        Dict with keys:
            extracted_interests: List[str]  — matched interest names
            interest_ids:        List[int]  — matched interest IDs
            model_used:          str
            prompt_tokens:       int
            completion_tokens:   int
            latency_ms:          float
            raw_llm_response:    str
    """
    logger.info(
        "[NvidiaNim.extract_interest_tags] ENTER | post_id=%s | content_len=%d | "
        "available_interests=%d | model=%s",
        post_id,
        len(content),
        len(available_interests),
        settings.NVIDIA_LLM_MODEL,
    )
    start_ts = time.perf_counter()

    # Build interest taxonomy string for the prompt
    interest_names = [i.name for i in available_interests]
    taxonomy_str = "\n".join(f"- {name}" for name in interest_names)
    logger.debug(
        "[NvidiaNim.extract_interest_tags] Taxonomy list | count=%d | first_5=%s",
        len(interest_names),
        interest_names[:5],
    )

    # Construct prompt
    system_prompt = (
        "You are a content classifier for a community platform. "
        "Your ONLY job is to identify which interests from the provided taxonomy list "
        "are relevant to the given post content. "
        "Return a JSON object with a single key 'interests' containing a list of "
        "interest names from the taxonomy. "
        "ONLY return interest names that are in the taxonomy. "
        "Return at most 5 interests. Return at least 1 if any match. "
        'Example response: {"interests": ["Photography", "Coffee Culture"]}'
    )

    user_prompt = (
        f"Post content:\n\"{content}\"\n\n"
        f"Taxonomy (pick from these only):\n{taxonomy_str}\n\n"
        "Return JSON only, no explanation."
    )

    # Start Langfuse generation trace
    generation_trace = None
    if langfuse_client:
        try:
            generation_trace = langfuse_client.generation(
                name="extract_interest_tags",
                model=settings.NVIDIA_LLM_MODEL,
                input=user_prompt,
                prompt=system_prompt,
                model_parameters={
                    "temperature": settings.NVIDIA_TEMPERATURE,
                    "max_tokens": settings.NVIDIA_MAX_TOKENS,
                    "post_id": post_id
                }
            )
            logger.debug("[NvidiaNim.extract_interest_tags] Langfuse trace created.")
        except Exception as lf_err:
            logger.warning("[NvidiaNim.extract_interest_tags] Langfuse trace start failed: %s", lf_err)

    logger.info(
        "[NvidiaNim.extract_interest_tags] LLM INPUT | model=%s | "
        "system_prompt_len=%d | user_prompt_len=%d",
        settings.NVIDIA_LLM_MODEL,
        len(system_prompt),
        len(user_prompt),
    )
    logger.debug(
        "[NvidiaNim.extract_interest_tags] SYSTEM PROMPT:\n%s", system_prompt
    )
    logger.debug(
        "[NvidiaNim.extract_interest_tags] USER PROMPT:\n%s", user_prompt
    )

    # Build request payload
    payload = {
        "model": settings.NVIDIA_LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": settings.NVIDIA_MAX_TOKENS,
        "temperature": settings.NVIDIA_TEMPERATURE,
    }

    logger.debug(
        "[NvidiaNim.extract_interest_tags] API REQUEST | url=%s/chat/completions | "
        "max_tokens=%d | temperature=%.2f",
        settings.NVIDIA_BASE_URL,
        settings.NVIDIA_MAX_TOKENS,
        settings.NVIDIA_TEMPERATURE,
    )

    # Make API call
    try:
        async with httpx.AsyncClient(timeout=settings.NVIDIA_REQUEST_TIMEOUT) as client:
            logger.info(
                "[NvidiaNim.extract_interest_tags] Making HTTP POST to NVIDIA NIM API"
            )
            api_call_start = time.perf_counter()

            response = await client.post(
                f"{settings.NVIDIA_BASE_URL}/chat/completions",
                headers=_get_headers(),
                json=payload,
            )

            api_latency_ms = (time.perf_counter() - api_call_start) * 1000
            logger.info(
                "[NvidiaNim.extract_interest_tags] API RESPONSE | status=%d | "
                "api_latency_ms=%.2f",
                response.status_code,
                api_latency_ms,
            )

            response.raise_for_status()
            response_data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error(
            "[NvidiaNim.extract_interest_tags] HTTP ERROR | status=%d | "
            "response=%s | post_id=%s",
            e.response.status_code,
            e.response.text[:500],
            post_id,
        )
        if generation_trace:
            try:
                generation_trace.end(
                    output=e.response.text[:500],
                    level="ERROR",
                    status_message=str(e)
                )
            except Exception as lf_err:
                logger.warning("[NvidiaNim] Langfuse error logging failed: %s", lf_err)
        return _fallback_tag_response(post_id, content, str(e))

    except httpx.TimeoutException as e:
        logger.error(
            "[NvidiaNim.extract_interest_tags] TIMEOUT ERROR | timeout=%ds | post_id=%s",
            settings.NVIDIA_REQUEST_TIMEOUT,
            post_id,
        )
        if generation_trace:
            try:
                generation_trace.end(
                    output=f"Timeout after {settings.NVIDIA_REQUEST_TIMEOUT}s",
                    level="ERROR",
                    status_message=str(e)
                )
            except Exception as lf_err:
                logger.warning("[NvidiaNim] Langfuse error logging failed: %s", lf_err)
        return _fallback_tag_response(post_id, content, f"Timeout after {settings.NVIDIA_REQUEST_TIMEOUT}s")

    except Exception as e:
        logger.error(
            "[NvidiaNim.extract_interest_tags] UNEXPECTED ERROR | error=%s: %s | post_id=%s",
            type(e).__name__,
            e,
            post_id,
        )
        if generation_trace:
            try:
                generation_trace.end(
                    output=str(e),
                    level="ERROR",
                    status_message=str(e)
                )
            except Exception as lf_err:
                logger.warning("[NvidiaNim] Langfuse error logging failed: %s", lf_err)
        return _fallback_tag_response(post_id, content, str(e))

    # Parse response
    total_latency_ms = (time.perf_counter() - start_ts) * 1000
    prompt_tokens = response_data.get("usage", {}).get("prompt_tokens", 0)
    completion_tokens = response_data.get("usage", {}).get("completion_tokens", 0)

    raw_content = response_data["choices"][0]["message"]["content"]
    logger.info(
        "[NvidiaNim.extract_interest_tags] LLM OUTPUT | raw_content='%s' | "
        "prompt_tokens=%d | completion_tokens=%d | total_latency_ms=%.2f",
        raw_content[:300],
        prompt_tokens,
        completion_tokens,
        total_latency_ms,
    )

    # Parse JSON from LLM output
    extracted_names, raw_response = _parse_llm_interest_response(raw_content)
    logger.info(
        "[NvidiaNim.extract_interest_tags] Parsed interests | count=%d | names=%s",
        len(extracted_names),
        extracted_names,
    )

    # End Langfuse trace on success
    if generation_trace:
        try:
            generation_trace.end(
                output=raw_content,
                usage={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens
                }
            )
            logger.debug("[NvidiaNim.extract_interest_tags] Langfuse trace ended successfully.")
        except Exception as lf_err:
            logger.warning("[NvidiaNim.extract_interest_tags] Langfuse trace end failed: %s", lf_err)

    # Map interest names → IDs
    interest_name_to_id = {i.name.lower(): i.id for i in available_interests}
    matched_ids = []
    matched_names = []
    for name in extracted_names:
        name_lower = name.lower()
        if name_lower in interest_name_to_id:
            iid = interest_name_to_id[name_lower]
            matched_ids.append(iid)
            matched_names.append(name)
            logger.debug(
                "[NvidiaNim.extract_interest_tags] Matched | name='%s' → id=%d",
                name,
                iid,
            )
        else:
            logger.warning(
                "[NvidiaNim.extract_interest_tags] LLM returned unknown interest '%s' — "
                "not in taxonomy | skipping",
                name,
            )

    result = {
        "post_id": post_id,
        "content_preview": content[:100] + "…" if len(content) > 100 else content,
        "extracted_interests": matched_names,
        "interest_ids": matched_ids,
        "model_used": settings.NVIDIA_LLM_MODEL,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "latency_ms": round(total_latency_ms, 2),
        "raw_llm_response": raw_response,
    }

    logger.info(
        "[NvidiaNim.extract_interest_tags] EXIT | matched_interests=%d | "
        "ids=%s | latency_ms=%.2f",
        len(matched_ids),
        matched_ids,
        total_latency_ms,
    )
    return result


def _parse_llm_interest_response(raw_content: str) -> tuple[List[str], str]:
    """
    Parse LLM output to extract interest names.

    Tries JSON parsing first; falls back to line-by-line extraction.

    Args:
        raw_content: Raw string from LLM

    Returns:
        (list_of_interest_names, raw_string_for_logging)
    """
    logger.debug(
        "[NvidiaNim._parse_llm_interest_response] ENTER | raw_content='%s'",
        raw_content[:500],
    )

    # Clean up: remove markdown code fences if present
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    logger.debug(
        "[NvidiaNim._parse_llm_interest_response] Cleaned content='%s'", cleaned[:300]
    )

    # Try JSON parse
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict) and "interests" in parsed:
            names = [str(n) for n in parsed["interests"] if n]
            logger.debug(
                "[NvidiaNim._parse_llm_interest_response] JSON parse success | names=%s", names
            )
            return names, raw_content
        elif isinstance(parsed, list):
            names = [str(n) for n in parsed if n]
            logger.debug(
                "[NvidiaNim._parse_llm_interest_response] JSON list parse | names=%s", names
            )
            return names, raw_content
    except json.JSONDecodeError as e:
        logger.warning(
            "[NvidiaNim._parse_llm_interest_response] JSON parse failed | error=%s | "
            "falling back to line extraction",
            e,
        )

    # Fallback: extract quoted strings or dash-prefixed lines
    import re
    quoted = re.findall(r'"([^"]+)"', cleaned)
    if quoted:
        logger.debug(
            "[NvidiaNim._parse_llm_interest_response] Regex fallback | found=%s", quoted
        )
        return quoted, raw_content

    # Last resort: split by comma or newline
    names = [n.strip().strip('"').strip("'") for n in re.split(r"[,\n]", cleaned) if n.strip()]
    logger.debug(
        "[NvidiaNim._parse_llm_interest_response] Split fallback | names=%s", names
    )
    return names[:5], raw_content


def _fallback_tag_response(post_id: Optional[int], content: str, error: str) -> Dict:
    """Return a safe empty response when LLM call fails."""
    logger.warning(
        "[NvidiaNim._fallback_tag_response] Returning empty fallback | "
        "post_id=%s | error=%s",
        post_id,
        error,
    )
    return {
        "post_id": post_id,
        "content_preview": content[:100],
        "extracted_interests": [],
        "interest_ids": [],
        "model_used": settings.NVIDIA_LLM_MODEL,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_ms": 0.0,
        "raw_llm_response": f"ERROR: {error}",
    }


# ---------------------------------------------------------------------------
# Semantic embeddings via NVIDIA NIM
# ---------------------------------------------------------------------------

async def generate_text_embedding(text: str) -> Optional[List[float]]:
    """
    Generate a semantic embedding for text using NVIDIA NIM embedding model.

    Model: nvidia/nv-embedqa-e5-v5

    Used ONLY for enriching user interest vectors with bio/profile text.
    The embedding is stored and later used for cosine similarity (pure Python).
    The embedding itself is NOT a ranking decision — it feeds the vector store.

    Args:
        text: Text to embed (user bio, post content, etc.)

    Returns:
        List of floats (embedding vector) or None on failure
    """
    logger.info(
        "[NvidiaNim.generate_text_embedding] ENTER | text_len=%d | model=%s",
        len(text),
        settings.NVIDIA_EMBED_MODEL,
    )
    start_ts = time.perf_counter()

    # Start Langfuse generation trace for embedding
    generation_trace = None
    if langfuse_client:
        try:
            generation_trace = langfuse_client.generation(
                name="generate_text_embedding",
                model=settings.NVIDIA_EMBED_MODEL,
                input={"text": text},
            )
            logger.debug("[NvidiaNim.generate_text_embedding] Langfuse embedding trace created.")
        except Exception as lf_err:
            logger.warning("[NvidiaNim.generate_text_embedding] Langfuse trace start failed: %s", lf_err)

    payload = {
        "model": settings.NVIDIA_EMBED_MODEL,
        "input": [text],
        "input_type": "passage",
        "encoding_format": "float",
        "truncate": "END",
    }

    logger.info(
        "[NvidiaNim.generate_text_embedding] EMBED INPUT | model=%s | "
        "text_preview='%s'",
        settings.NVIDIA_EMBED_MODEL,
        text[:100],
    )

    try:
        async with httpx.AsyncClient(timeout=settings.NVIDIA_REQUEST_TIMEOUT) as client:
            logger.debug("[NvidiaNim.generate_text_embedding] Making HTTP POST to embeddings endpoint")
            response = await client.post(
                f"{settings.NVIDIA_BASE_URL}/embeddings",
                headers=_get_headers(),
                json=payload,
            )
            response.raise_for_status()
            response_data = response.json()

    except Exception as e:
        logger.error(
            "[NvidiaNim.generate_text_embedding] API ERROR | error=%s: %s",
            type(e).__name__,
            e,
        )
        if generation_trace:
            try:
                generation_trace.end(
                    output=str(e),
                    level="ERROR",
                    status_message=str(e)
                )
            except Exception as lf_err:
                logger.warning("[NvidiaNim] Langfuse error logging failed: %s", lf_err)
        return None

    latency_ms = (time.perf_counter() - start_ts) * 1000

    embedding = response_data["data"][0]["embedding"]

    # End Langfuse trace on success
    if generation_trace:
        try:
            generation_trace.end(
                output={"embedding_dimension": len(embedding)},
                usage={
                    "prompt_tokens": len(text.split()), # approximate token usage estimation
                }
            )
            logger.debug("[NvidiaNim.generate_text_embedding] Langfuse embedding trace ended successfully.")
        except Exception as lf_err:
            logger.warning("[NvidiaNim.generate_text_embedding] Langfuse trace end failed: %s", lf_err)

    logger.info(
        "[NvidiaNim.generate_text_embedding] EMBED OUTPUT | dim=%d | "
        "first_3=[%.4f, %.4f, %.4f] | latency_ms=%.2f",
        len(embedding),
        embedding[0] if len(embedding) > 0 else 0,
        embedding[1] if len(embedding) > 1 else 0,
        embedding[2] if len(embedding) > 2 else 0,
        latency_ms,
    )

    logger.info(
        "[NvidiaNim.generate_text_embedding] EXIT | embedding_dim=%d | latency_ms=%.2f",
        len(embedding),
        latency_ms,
    )
    return embedding
