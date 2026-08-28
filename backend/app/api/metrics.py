"""
api/metrics.py
==============
API endpoints for overall system analytics and metrics dashboard.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.entities import Business, Club, Event, Interaction, Post, User
from app.models.schemas import SystemMetrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("", response_model=SystemMetrics)
async def get_system_metrics(db: AsyncSession = Depends(get_db)):
    """Fetch system-wide metrics for the analytics dashboard."""
    logger.info("[API.get_system_metrics] ENTER")
    start_time = datetime.utcnow()

    # Query counts
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    post_count = (await db.execute(select(func.count(Post.id)))).scalar() or 0
    club_count = (await db.execute(select(func.count(Club.id)))).scalar() or 0
    biz_count = (await db.execute(select(func.count(Business.id)))).scalar() or 0
    event_count = (await db.execute(select(func.count(Event.id)))).scalar() or 0
    interaction_count = (await db.execute(select(func.count(Interaction.id)))).scalar() or 0

    # Query average trust
    avg_trust = (await db.execute(select(func.avg(User.trust_score)))).scalar() or 0.5

    # Query cold start users
    cold_start_users = (
        await db.execute(select(func.count(User.id)).where(User.interaction_count < 5))
    ).scalar() or 0

    # Count LLM tags
    llm_calls = (await db.execute(select(func.count(Post.id)).where(Post.llm_tagged == True))).scalar() or 0

    logger.info(
        "[API.get_system_metrics] EXIT | users=%d | posts=%d | interactions=%d | avg_trust=%.2f",
        user_count, post_count, interaction_count, avg_trust
    )

    return SystemMetrics(
        total_users=user_count,
        total_posts=post_count,
        total_clubs=club_count,
        total_businesses=biz_count,
        total_events=event_count,
        total_interactions=interaction_count,
        avg_trust_score=round(avg_trust, 4),
        avg_feed_relevance=0.75, # placeholder simulation
        cold_start_users=cold_start_users,
        llm_calls_today=llm_calls,
        generated_at=datetime.utcnow()
    )
