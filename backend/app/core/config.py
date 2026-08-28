"""
core/config.py
==============
Centralised application configuration loaded from .env via pydantic-settings.
Every setting is typed and documented.  Import `settings` anywhere in the app.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    Precedence (highest → lowest):
        1. Environment variables
        2. .env file in the backend/ directory
        3. Default values declared here
    """

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --------------------------------------------------------------------------
    # Application
    # --------------------------------------------------------------------------
    APP_NAME: str = "SodioInterestGraph"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Interest Graph Engine — Community Platform"
    DEBUG: bool = True
    LOG_LEVEL: str = "DEBUG"

    # --------------------------------------------------------------------------
    # Server
    # --------------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Return CORS origins as a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # --------------------------------------------------------------------------
    # NVIDIA NIM
    # LLM is ONLY used for:
    #   1. NLP interest-tag extraction from post text
    #   2. Semantic embedding generation for interest vectors
    # ALL ranking math, decay formulas, trust scores = pure Python
    # --------------------------------------------------------------------------
    NVIDIA_API_KEY: str = "your_nvidia_api_key_here"
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_LLM_MODEL: str = "meta/llama-3.1-70b-instruct"
    NVIDIA_EMBED_MODEL: str = "nvidia/nv-embedqa-e5-v5"
    NVIDIA_MAX_TOKENS: int = 512
    NVIDIA_TEMPERATURE: float = 0.1
    NVIDIA_REQUEST_TIMEOUT: int = 30

    # --------------------------------------------------------------------------
    # Langfuse Monitoring
    # --------------------------------------------------------------------------
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"


    # --------------------------------------------------------------------------
    # Database
    # --------------------------------------------------------------------------
    DATABASE_URL: str = "sqlite:///./sodio.db"

    # --------------------------------------------------------------------------
    # Ranking Weights  (Section 4 of design doc)
    # Must collectively sum to 1.0 (enforced at runtime, not here)
    # --------------------------------------------------------------------------
    WEIGHT_RELEVANCE: float = 0.30
    WEIGHT_TRUST: float = 0.20
    WEIGHT_AUTHORITY: float = 0.15
    WEIGHT_FRESHNESS: float = 0.15
    WEIGHT_PROXIMITY: float = 0.10
    WEIGHT_ENGAGEMENT: float = 0.05
    WEIGHT_INTENT: float = 0.05

    # --------------------------------------------------------------------------
    # Signal Decay  (Section 3 of design doc)
    # recency_factor = exp(-lambda * days_since_last_interaction)
    # --------------------------------------------------------------------------
    DECAY_LAMBDA_EXPLICIT: float = 0.01   # months-scale decay
    DECAY_LAMBDA_IMPLICIT: float = 0.10   # days-scale decay
    DECAY_LAMBDA_MEDIUM: float = 0.05     # week-scale decay

    # --------------------------------------------------------------------------
    # Edge Weight Coefficients  (Section 3)
    # edge_weight = (alpha * explicit_base)
    #             + (beta  * implicit_score * trust_multiplier)
    #             + (gamma * recency_factor)
    # --------------------------------------------------------------------------
    EDGE_WEIGHT_ALPHA: float = 0.5
    EDGE_WEIGHT_BETA: float = 0.3
    EDGE_WEIGHT_GAMMA: float = 0.2

    # --------------------------------------------------------------------------
    # MMR Diversity Re-ranking  (Section 4)
    # mmr_score = lambda * relevance - (1 - lambda) * max_similarity_to_selected
    # --------------------------------------------------------------------------
    MMR_LAMBDA: float = 0.7
    DIVERSITY_SLOT_FRACTION: float = 0.20

    # --------------------------------------------------------------------------
    # Trust Propagation  (Section 6 — PageRank-style)
    # trust_t+1 = (1 - damping) + damping * sum(trust_j / out_degree_j)
    # --------------------------------------------------------------------------
    TRUST_DAMPING_FACTOR: float = 0.85
    TRUST_PROPAGATION_ITERATIONS: int = 20
    TRUST_MIN_SCORE: float = 0.10
    TRUST_MAX_SCORE: float = 1.00
    VERIFIED_USER_TRUST_BOOST: float = 0.15
    VERIFIED_BUSINESS_TRUST_BOOST: float = 0.20

    # --------------------------------------------------------------------------
    # Feed & Recommendation
    # --------------------------------------------------------------------------
    DEFAULT_FEED_SIZE: int = 20
    MAX_FEED_SIZE: int = 50
    COLD_START_THRESHOLD: int = 5
    COMMERCIAL_SLOT_FRACTION: float = 0.20
    EXPLORE_SLOT_FRACTION: float = 0.10
    MAX_HOPS_GRAPH_EXPLORATION: int = 3

    # --------------------------------------------------------------------------
    # Spam & Safety Penalties
    # --------------------------------------------------------------------------
    SPAM_RISK_HIGH_PENALTY: float = 0.40
    SPAM_RISK_MEDIUM_PENALTY: float = 0.20
    VELOCITY_ANOMALY_WINDOW_MINUTES: int = 5
    VELOCITY_ANOMALY_THRESHOLD: int = 50


@lru_cache()
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    _log = logging.getLogger(__name__)
    _log.info("[Config] Loading settings from .env file")
    s = Settings()
    _log.info(
        "[Config] Settings loaded | APP_NAME=%s | APP_VERSION=%s | DEBUG=%s | LOG_LEVEL=%s",
        s.APP_NAME,
        s.APP_VERSION,
        s.DEBUG,
        s.LOG_LEVEL,
    )
    _log.info(
        "[Config] Ranking weights | relevance=%.2f | trust=%.2f | authority=%.2f "
        "| freshness=%.2f | proximity=%.2f | engagement=%.2f | intent=%.2f",
        s.WEIGHT_RELEVANCE,
        s.WEIGHT_TRUST,
        s.WEIGHT_AUTHORITY,
        s.WEIGHT_FRESHNESS,
        s.WEIGHT_PROXIMITY,
        s.WEIGHT_ENGAGEMENT,
        s.WEIGHT_INTENT,
    )
    _log.info(
        "[Config] Decay lambdas | explicit=%.3f | implicit=%.3f | medium=%.3f",
        s.DECAY_LAMBDA_EXPLICIT,
        s.DECAY_LAMBDA_IMPLICIT,
        s.DECAY_LAMBDA_MEDIUM,
    )
    _log.info(
        "[Config] NVIDIA NIM | base_url=%s | llm_model=%s | embed_model=%s",
        s.NVIDIA_BASE_URL,
        s.NVIDIA_LLM_MODEL,
        s.NVIDIA_EMBED_MODEL,
    )
    return s


# Module-level singleton — import this everywhere
settings = get_settings()
