"""
models/schemas.py
=================
Pydantic v2 schemas for all API request/response models.
Keeps ORM layer separate from transport layer.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------

class OrmBase(BaseModel):
    """Base model with ORM mode enabled."""
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Interest / Domain
# ---------------------------------------------------------------------------

class DomainOut(OrmBase):
    id: int
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None


class InterestOut(OrmBase):
    id: int
    name: str
    domain_id: int
    parent_interest_id: Optional[int] = None
    description: Optional[str] = None
    domain: Optional[DomainOut] = None


class InterestCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    domain_id: int
    parent_interest_id: Optional[int] = None
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    display_name: str = Field(..., min_length=1, max_length=150)
    email: str = Field(..., min_length=5, max_length=200)
    bio: Optional[str] = None
    location_city: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    user_type: str = Field(default="community")
    interest_ids: List[int] = Field(
        default=[], description="Interest IDs selected during onboarding"
    )

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        allowed = {"community", "business", "creator", "verified"}
        if v not in allowed:
            raise ValueError(f"user_type must be one of {allowed}")
        return v


class UserOut(OrmBase):
    id: int
    username: str
    display_name: str
    email: str
    bio: Optional[str] = None
    location_city: Optional[str] = None
    user_type: str
    is_verified: bool
    trust_score: float
    interaction_count: int
    created_at: datetime
    interests: List[InterestOut] = []


class UserProfile(UserOut):
    """Extended profile including computed vectors."""
    interest_vector: Optional[List[float]] = None
    interest_vector_labels: Optional[List[str]] = None  # human-readable labels


# ---------------------------------------------------------------------------
# Club
# ---------------------------------------------------------------------------

class ClubCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = None
    location_city: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    interest_ids: List[int] = []
    is_public: bool = True


class ClubOut(OrmBase):
    id: int
    name: str
    description: Optional[str] = None
    location_city: Optional[str] = None
    member_count: int
    is_public: bool
    trust_score: float
    authority_score: float
    created_at: datetime
    interests: List[InterestOut] = []


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------

class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    location_city: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    website: Optional[str] = None
    interest_ids: List[int] = []


class BusinessOut(OrmBase):
    id: int
    name: str
    description: Optional[str] = None
    location_city: Optional[str] = None
    is_verified: bool
    trust_score: float
    authority_score: float
    spam_risk_score: float
    months_active: int
    created_at: datetime
    interests: List[InterestOut] = []


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    location_city: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    host_club_id: Optional[int] = None
    host_business_id: Optional[int] = None
    interest_ids: List[int] = []


class EventOut(OrmBase):
    id: int
    title: str
    description: Optional[str] = None
    location_city: Optional[str] = None
    starts_at: Optional[datetime] = None
    rsvp_count: int
    attendance_count: int
    created_at: datetime
    interests: List[InterestOut] = []


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class PostCreate(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    media_url: Optional[str] = None
    post_type: str = Field(default="community")
    author_id: int
    club_id: Optional[int] = None
    business_id: Optional[int] = None
    event_id: Optional[int] = None
    interest_ids: Optional[List[int]] = None  # If None, LLM will auto-tag
    auto_tag: bool = Field(
        default=True,
        description="If True, send content to NVIDIA NIM for interest extraction"
    )

    @field_validator("post_type")
    @classmethod
    def validate_post_type(cls, v: str) -> str:
        allowed = {"community", "business", "event_promo"}
        if v not in allowed:
            raise ValueError(f"post_type must be one of {allowed}")
        return v


class PostOut(OrmBase):
    id: int
    title: Optional[str] = None
    content: str
    post_type: str
    author_id: int
    club_id: Optional[int] = None
    view_count: int
    like_count: int
    comment_count: int
    share_count: int
    save_count: int
    authority_score: float
    engagement_quality_score: float
    spam_risk_score: float
    llm_tagged: bool
    llm_tag_model: Optional[str] = None
    llm_tag_latency_ms: Optional[float] = None
    is_flagged: bool
    created_at: datetime
    interests: List[InterestOut] = []


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

class InteractionCreate(BaseModel):
    user_id: int
    entity_type: str = Field(
        ..., description="post | club | business | event | user"
    )
    entity_id: int
    interaction_type: str = Field(
        ...,
        description="view|like|comment|share|save|rsvp|attended|contact_click|skip|report"
    )
    session_id: Optional[str] = None
    duration_seconds: Optional[float] = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        allowed = {"post", "club", "business", "event", "user"}
        if v not in allowed:
            raise ValueError(f"entity_type must be one of {allowed}")
        return v

    @field_validator("interaction_type")
    @classmethod
    def validate_interaction_type(cls, v: str) -> str:
        allowed = {
            "view", "like", "comment", "share", "save",
            "rsvp", "attended", "contact_click", "skip", "report"
        }
        if v not in allowed:
            raise ValueError(f"interaction_type must be one of {allowed}")
        return v


class InteractionOut(OrmBase):
    id: int
    user_id: int
    entity_type: str
    entity_id: int
    interaction_type: str
    raw_weight: float
    trust_weighted: float
    effective_weight: float
    created_at: datetime


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

class RankedPost(BaseModel):
    """A ranked post with full score breakdown for explainability."""
    post: PostOut
    author: Optional[UserOut] = None

    # Composite score (0-1)
    final_score: float

    # Score components (Section 4 of design doc)
    relevance: float = Field(description="Cosine similarity of post interests vs user vector")
    trust: float = Field(description="Author trust score propagated")
    authority: float = Field(description="Post authority from engagement quality")
    freshness: float = Field(description="exp(-lambda * hours_since_created / 24)")
    proximity: float = Field(description="Location proximity score (0-1)")
    engagement_quality: float = Field(description="Weighted engagement rate")
    intent_match: float = Field(description="Intent signal from similar users")
    spam_risk_penalty: float = Field(description="Deducted spam penalty")
    diversity_boost: bool = Field(description="True if selected via MMR diversity pass")

    # Debug info
    score_formula: str = Field(
        description="Human-readable formula with substituted values"
    )


class FeedResponse(BaseModel):
    user_id: int
    is_cold_start: bool
    total_candidates: int
    returned_count: int
    feed: List[RankedPost]
    generated_at: datetime
    feed_strategy: str = Field(
        description="personalized | cold_start | mixed"
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

class RecommendedItem(BaseModel):
    entity_type: str   # club | business | event | user
    entity_id: int
    name: str
    score: float
    reason: str        # Human-readable explanation


class RecommendationsResponse(BaseModel):
    user_id: int
    clubs: List[RecommendedItem]
    businesses: List[RecommendedItem]
    events: List[RecommendedItem]
    people: List[RecommendedItem]
    generated_at: datetime


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    id: str               # "user_1", "interest_3", etc.
    label: str
    node_type: str        # user | interest | domain | club | business | event | post
    trust_score: Optional[float] = None
    properties: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str        # HAS_INTEREST | MEMBER_OF | FOLLOWS | ENGAGED_WITH | SIMILAR_TO
    weight: float
    properties: Dict[str, Any] = {}


class GraphResponse(BaseModel):
    user_id: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    depth: int
    node_count: int
    edge_count: int


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class SystemMetrics(BaseModel):
    total_users: int
    total_posts: int
    total_clubs: int
    total_businesses: int
    total_events: int
    total_interactions: int
    avg_trust_score: float
    avg_feed_relevance: float
    cold_start_users: int
    llm_calls_today: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# LLM Tag
# ---------------------------------------------------------------------------

class TagPostRequest(BaseModel):
    content: str = Field(..., min_length=10)
    post_id: Optional[int] = None


class TagPostResponse(BaseModel):
    post_id: Optional[int]
    content_preview: str
    extracted_interests: List[str]
    interest_ids: List[int]
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    raw_llm_response: str
