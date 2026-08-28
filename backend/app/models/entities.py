"""
models/entities.py
==================
SQLAlchemy ORM models — the relational (Postgres / SQLite) source-of-truth
for all core entities described in Section 1 and 3 of the design document.

Entity hierarchy (mirrors the graph nodes):
  User → Interest/Domain → Club → Business → Event → Post
  Interaction = typed, weighted, decaying edge between User and any entity
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Association / junction tables (many-to-many)
# ---------------------------------------------------------------------------

user_interest_table = Table(
    "user_interests",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("interest_id", Integer, ForeignKey("interests.id"), primary_key=True),
    Column("weight", Float, default=1.0, comment="Explicit weight from onboarding (0-1)"),
    Column("source", String(50), default="onboarding"),
    Column("created_at", DateTime, default=datetime.utcnow),
)

post_interest_table = Table(
    "post_interests",
    Base.metadata,
    Column("post_id", Integer, ForeignKey("posts.id"), primary_key=True),
    Column("interest_id", Integer, ForeignKey("interests.id"), primary_key=True),
    Column("confidence", Float, default=1.0, comment="LLM tag confidence (0-1)"),
    Column("tagged_by", String(50), default="manual"),  # manual | llm | both
)

club_interest_table = Table(
    "club_interests",
    Base.metadata,
    Column("club_id", Integer, ForeignKey("clubs.id"), primary_key=True),
    Column("interest_id", Integer, ForeignKey("interests.id"), primary_key=True),
)

business_interest_table = Table(
    "business_interests",
    Base.metadata,
    Column("business_id", Integer, ForeignKey("businesses.id"), primary_key=True),
    Column("interest_id", Integer, ForeignKey("interests.id"), primary_key=True),
)

event_interest_table = Table(
    "event_interests",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("interest_id", Integer, ForeignKey("interests.id"), primary_key=True),
)

user_follows_table = Table(
    "user_follows",
    Base.metadata,
    Column("follower_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("followee_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)

user_club_table = Table(
    "user_clubs",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("club_id", Integer, ForeignKey("clubs.id"), primary_key=True),
    Column("joined_at", DateTime, default=datetime.utcnow),
    Column("role", String(50), default="member"),
)


# ---------------------------------------------------------------------------
# Domain taxonomy (top-level category)
# ---------------------------------------------------------------------------

class Domain(Base):
    """
    Top-level interest domain (e.g. Arts, Technology, Sports).
    Part of the hierarchical taxonomy: Domain → Interest → Sub-interest.
    """

    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # One domain has many interests
    interests: Mapped[List["Interest"]] = relationship("Interest", back_populates="domain")

    def __repr__(self) -> str:
        return f"<Domain id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# Interest (taxonomy node)
# ---------------------------------------------------------------------------

class Interest(Base):
    """
    Interest taxonomy node.  Lives one level below Domain.
    Carries a co-occurrence vector (serialised JSON) that enables
    graph-based exploration (Section 3 — SIMILAR_TO edges).
    """

    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    domain_id: Mapped[int] = mapped_column(Integer, ForeignKey("domains.id"), nullable=False)
    parent_interest_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("interests.id"), nullable=True,
        comment="Sub-interest parent (None if top-level within domain)"
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Serialised list of co-occurring interest IDs (JSON string) for SIMILAR_TO edges
    co_occurrence_ids: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON list of co-occurring interest IDs"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    domain: Mapped["Domain"] = relationship("Domain", back_populates="interests")
    sub_interests: Mapped[List["Interest"]] = relationship(
        "Interest", foreign_keys=[parent_interest_id]
    )

    def __repr__(self) -> str:
        return f"<Interest id={self.id} name={self.name!r} domain_id={self.domain_id}>"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    """
    Core identity node.
    Carries both an explicit interest set (from onboarding) and computed
    interest_vector (serialised numpy float array, updated nightly).
    Trust score is maintained by TrustScorer and updated incrementally.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    user_type: Mapped[str] = mapped_column(
        String(30), default="community",
        comment="community | business | creator | verified"
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Trust score (0-1) — maintained by TrustScorer (Section 6)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)

    # Serialised interest vector (JSON float array — index maps to interest IDs)
    interest_vector: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON float array; index = interest_id; value = weight"
    )
    # Serialised NVIDIA embedding (JSON float array)
    embedding: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON float array from nvidia/nv-embedqa-e5-v5"
    )

    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    spam_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    interests: Mapped[List["Interest"]] = relationship(
        "Interest", secondary=user_interest_table
    )
    clubs: Mapped[List["Club"]] = relationship(
        "Club", secondary=user_club_table, back_populates="members"
    )
    follows: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_follows_table,
        primaryjoin="User.id == user_follows_table.c.follower_id",
        secondaryjoin="User.id == user_follows_table.c.followee_id",
    )
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="author")
    interactions: Mapped[List["Interaction"]] = relationship("Interaction", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} trust={self.trust_score:.2f}>"


# ---------------------------------------------------------------------------
# Club
# ---------------------------------------------------------------------------

class Club(Base):
    """Community node — aggregates members who share interests."""

    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    member_count: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    authority_score: Mapped[float] = mapped_column(
        Float, default=0.5,
        comment="Normalised by member_count and engagement rate"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interests: Mapped[List["Interest"]] = relationship(
        "Interest", secondary=club_interest_table
    )
    members: Mapped[List["User"]] = relationship(
        "User", secondary=user_club_table, back_populates="clubs"
    )
    posts: Mapped[List["Post"]] = relationship("Post", back_populates="club")

    def __repr__(self) -> str:
        return f"<Club id={self.id} name={self.name!r} members={self.member_count}>"


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------

class Business(Base):
    """
    Commercial node.
    Has an interest/category profile plus trust and verification attributes.
    Hard separated from community content via slot-budget (Section 4, 6).
    """

    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.3)
    authority_score: Mapped[float] = mapped_column(Float, default=0.3)
    spam_risk_score: Mapped[float] = mapped_column(
        Float, default=0.0, comment="0=clean 1=likely spam"
    )
    months_active: Mapped[int] = mapped_column(Integer, default=0)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interests: Mapped[List["Interest"]] = relationship(
        "Interest", secondary=business_interest_table
    )

    def __repr__(self) -> str:
        return f"<Business id={self.id} name={self.name!r} trust={self.trust_score:.2f}>"


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class Event(Base):
    """Time-bound node linked to location, interests, and optionally a club/business."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rsvp_count: Mapped[int] = mapped_column(Integer, default=0)
    attendance_count: Mapped[int] = mapped_column(Integer, default=0)
    host_club_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("clubs.id"), nullable=True
    )
    host_business_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("businesses.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    interests: Mapped[List["Interest"]] = relationship(
        "Interest", secondary=event_interest_table
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} title={self.title!r}>"


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class Post(Base):
    """
    Content node — the primary feed unit.
    Interest tags applied manually or via NVIDIA NIM NLP (the ONLY LLM touchpoint
    in the content pipeline).
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    post_type: Mapped[str] = mapped_column(
        String(30), default="community",
        comment="community | business | event_promo"
    )
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    club_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("clubs.id"), nullable=True
    )
    business_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("businesses.id"), nullable=True
    )
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=True
    )

    # Engagement counters
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    save_count: Mapped[int] = mapped_column(Integer, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, default=0)

    # Computed scores (updated by ranking service)
    authority_score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    spam_risk_score: Mapped[float] = mapped_column(Float, default=0.0)

    # LLM tagging metadata
    llm_tagged: Mapped[bool] = mapped_column(Boolean, default=False)
    llm_tag_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    llm_tag_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    author: Mapped["User"] = relationship("User", back_populates="posts")
    club: Mapped[Optional["Club"]] = relationship("Club", back_populates="posts")
    interests: Mapped[List["Interest"]] = relationship(
        "Interest", secondary=post_interest_table
    )

    def __repr__(self) -> str:
        return f"<Post id={self.id} author_id={self.author_id} type={self.post_type!r}>"


# ---------------------------------------------------------------------------
# Interaction (typed edge — Section 1, 3)
# ---------------------------------------------------------------------------

class Interaction(Base):
    """
    Typed, weighted, decaying edge produced by user behaviour.
    Not a node — a record of user action that updates graph edge weights.

    Interaction types and signal strengths (Section 2):
      - view        : weak implicit
      - like        : medium implicit
      - comment     : medium implicit
      - share       : medium implicit
      - save        : medium implicit
      - rsvp        : strong implicit
      - attended    : strong implicit
      - contact_click: medium-strong implicit
      - skip        : negative signal
      - report      : strong negative signal
    """

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="post | club | business | event | user"
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="view|like|comment|share|save|rsvp|attended|contact_click|skip|report"
    )

    # Base signal weight BEFORE trust multiplication and decay
    raw_weight: Mapped[float] = mapped_column(
        Float, default=1.0,
        comment="Signal strength before trust multiplication and decay"
    )
    # Weight after trust multiplication (trust_score * raw_weight)
    trust_weighted: Mapped[float] = mapped_column(Float, default=1.0)
    # Final effective weight including recency decay
    effective_weight: Mapped[float] = mapped_column(Float, default=1.0)

    session_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Current session ID for session-vector updates"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="For view interactions: time spent"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    user: Mapped["User"] = relationship("User", back_populates="interactions")

    def __repr__(self) -> str:
        return (
            f"<Interaction id={self.id} user={self.user_id} "
            f"type={self.interaction_type!r} entity={self.entity_type}/{self.entity_id}>"
        )
