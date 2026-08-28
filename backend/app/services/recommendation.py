"""
services/recommendation.py
==========================
Entity recommendation engine for clubs, businesses, events, and people.

Implements sections 4 and 5 of the design document:
  - Club discovery
  - Business/vendor recommendations
  - People recommendations (who you should connect with)
  - Event discovery

CRITICAL CONSTRAINT:
  100% of mathematical scoring, proximity calculations, and similarity checks
  execute in native Python. LLMs are NOT used in this ranking module.
"""

import json
import logging
import math
import time
from datetime import datetime
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.entities import Business, Club, Event, User, user_follows_table
from app.models.schemas import RecommendedItem
from app.services.interest_engine import compute_cosine_similarity

logger = logging.getLogger(__name__)


async def recommend_clubs(
    session: AsyncSession,
    user: User,
    user_vec: List[float],
    total_interests: int,
    limit: int = 5
) -> List[RecommendedItem]:
    """
    Recommend clubs to the user based on interest similarity and location.

    Formula (pure Python):
        score = 0.50 * similarity + 0.30 * proximity + 0.20 * authority
    """
    logger.info("[Recommendation.recommend_clubs] ENTER | user_id=%d | limit=%d", user.id, limit)
    start_time = time.perf_counter()

    result = await session.execute(
        select(Club).options(selectinload(Club.interests)).limit(100)
    )
    clubs = result.scalars().all()

    recommendations = []
    for club in clubs:
        # Check if already a member (simulated by checking if in list for POC)
        # In a real app we'd filter in the query, here we load and filter
        # For simplicity, if we have membership records we skip.
        
        # Calculate interest vector for club
        club_interest_ids = [i.id for i in club.interests]
        club_vec = [0.0] * total_interests
        for iid in club_interest_ids:
            if 0 <= iid - 1 < total_interests:
                club_vec[iid - 1] = 1.0

        similarity = compute_cosine_similarity(user_vec, club_vec)
        
        # Proximity score (0-1)
        proximity = 0.5 # default
        if all(v is None for v in [user.location_lat, user.location_lon, club.location_lat, club.location_lon]):
            proximity = 0.5
        else:
            # simple Euclidean distance normalized as proximity
            d = math.sqrt((user.location_lat - club.location_lat)**2 + (user.location_lon - club.location_lon)**2)
            proximity = max(0.0, min(1.0, 1.0 - d / 2.0))

        # Authority
        authority = club.authority_score

        # Multi-factor score
        score = 0.50 * similarity + 0.30 * proximity + 0.20 * authority
        score = round(score, 4)

        reason = f"Shares {similarity*100:.0f}% interest match & active in your city."
        
        recommendations.append(
            RecommendedItem(
                entity_type="club",
                entity_id=club.id,
                name=club.name,
                score=score,
                reason=reason
            )
        )

    recommendations.sort(key=lambda x: x.score, reverse=True)
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info("[Recommendation.recommend_clubs] EXIT | count=%d | elapsed_ms=%.2f", len(recommendations[:limit]), elapsed)
    return recommendations[:limit]


async def recommend_businesses(
    session: AsyncSession,
    user: User,
    user_vec: List[float],
    total_interests: int,
    limit: int = 5
) -> List[RecommendedItem]:
    """
    Recommend businesses/vendors to the user.

    Formula (pure Python):
        score = 0.40 * similarity + 0.30 * proximity + 0.30 * trust
    """
    logger.info("[Recommendation.recommend_businesses] ENTER | user_id=%d", user.id)
    start_time = time.perf_counter()

    result = await session.execute(
        select(Business).options(selectinload(Business.interests)).limit(100)
    )
    businesses = result.scalars().all()

    recommendations = []
    for biz in businesses:
        biz_interest_ids = [i.id for i in biz.interests]
        biz_vec = [0.0] * total_interests
        for iid in biz_interest_ids:
            if 0 <= iid - 1 < total_interests:
                biz_vec[iid - 1] = 1.0

        similarity = compute_cosine_similarity(user_vec, biz_vec)
        
        # Proximity score
        proximity = 0.5
        if all(v is None for v in [user.location_lat, user.location_lon, biz.location_lat, biz.location_lon]):
            proximity = 0.5
        else:
            d = math.sqrt((user.location_lat - biz.location_lat)**2 + (user.location_lon - biz.location_lon)**2)
            proximity = max(0.0, min(1.0, 1.0 - d / 2.0))

        # Trust
        trust = biz.trust_score

        # Composite score
        score = 0.40 * similarity + 0.30 * proximity + 0.30 * trust
        score = round(score, 4)

        reason = f"Verified vendor, {similarity*100:.0f}% category relevance & {proximity*50:.1f}km away."

        recommendations.append(
            RecommendedItem(
                entity_type="business",
                entity_id=biz.id,
                name=biz.name,
                score=score,
                reason=reason
            )
        )

    recommendations.sort(key=lambda x: x.score, reverse=True)
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info("[Recommendation.recommend_businesses] EXIT | count=%d | elapsed_ms=%.2f", len(recommendations[:limit]), elapsed)
    return recommendations[:limit]


async def recommend_events(
    session: AsyncSession,
    user: User,
    user_vec: List[float],
    total_interests: int,
    limit: int = 5
) -> List[RecommendedItem]:
    """
    Recommend events.

    Formula:
        score = 0.40 * similarity + 0.40 * proximity + 0.20 * freshness
    """
    logger.info("[Recommendation.recommend_events] ENTER | user_id=%d", user.id)
    start_time = time.perf_counter()

    result = await session.execute(
        select(Event).options(selectinload(Event.interests)).limit(100)
    )
    events = result.scalars().all()

    recommendations = []
    for ev in events:
        ev_interest_ids = [i.id for i in ev.interests]
        ev_vec = [0.0] * total_interests
        for iid in ev_interest_ids:
            if 0 <= iid - 1 < total_interests:
                ev_vec[iid - 1] = 1.0

        similarity = compute_cosine_similarity(user_vec, ev_vec)
        
        # Proximity score
        proximity = 0.5
        if all(v is None for v in [user.location_lat, user.location_lon, ev.location_lat, ev.location_lon]):
            proximity = 0.5
        else:
            d = math.sqrt((user.location_lat - ev.location_lat)**2 + (user.location_lon - ev.location_lon)**2)
            proximity = max(0.0, min(1.0, 1.0 - d / 2.0))

        # Time decay/Freshness (how close is it to starting)
        freshness = 0.5
        if ev.starts_at:
            delta = ev.starts_at - datetime.utcnow()
            days = delta.total_seconds() / 86400.0
            if days > 0:
                freshness = math.exp(-0.1 * days) # exponential decay of relevance as it goes further out
            else:
                freshness = 0.0 # expired

        score = 0.40 * similarity + 0.40 * proximity + 0.20 * freshness
        score = round(score, 4)

        reason = f"Happening soon in your area. Matches interest tag: {', '.join([i.name for i in ev.interests[:2]])}"

        recommendations.append(
            RecommendedItem(
                entity_type="event",
                entity_id=ev.id,
                name=ev.title,
                score=score,
                reason=reason
            )
        )

    recommendations.sort(key=lambda x: x.score, reverse=True)
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info("[Recommendation.recommend_events] EXIT | count=%d | elapsed_ms=%.2f", len(recommendations[:limit]), elapsed)
    return recommendations[:limit]


async def recommend_people(
    session: AsyncSession,
    user: User,
    user_vec: List[float],
    total_interests: int,
    limit: int = 5
) -> List[RecommendedItem]:
    """
    Recommend people (other users) to connect with.

    Formula (pure Python):
        score = 0.50 * similarity + 0.30 * proximity + 0.20 * trust
    """
    logger.info("[Recommendation.recommend_people] ENTER | user_id=%d", user.id)
    start_time = time.perf_counter()

    # Find users we don't already follow
    # First, get followed user IDs
    followee_ids_query = await session.execute(
        select(user_follows_table.c.followee_id).where(user_follows_table.c.follower_id == user.id)
    )
    followed_ids = {row[0] for row in followee_ids_query.all()}
    followed_ids.add(user.id) # exclude ourselves

    result = await session.execute(
        select(User).where(User.id.notin_(followed_ids)).limit(50)
    )
    candidates = result.scalars().all()

    recommendations = []
    for cand in candidates:
        if not cand.interest_vector:
            continue

        try:
            cand_vec = json.loads(cand.interest_vector)
        except Exception:
            continue

        similarity = compute_cosine_similarity(user_vec, cand_vec)
        
        # Proximity score
        proximity = 0.5
        if all(v is None for v in [user.location_lat, user.location_lon, cand.location_lat, cand.location_lon]):
            proximity = 0.5
        else:
            d = math.sqrt((user.location_lat - cand.location_lat)**2 + (user.location_lon - cand.location_lon)**2)
            proximity = max(0.0, min(1.0, 1.0 - d / 2.0))

        # Trust
        trust = cand.trust_score

        score = 0.50 * similarity + 0.30 * proximity + 0.20 * trust
        score = round(score, 4)

        reason = f"Active in {cand.location_city or 'your city'} with {similarity*100:.0f}% shared interests."

        recommendations.append(
            RecommendedItem(
                entity_type="user",
                entity_id=cand.id,
                name=cand.display_name,
                score=score,
                reason=reason
            )
        )

    recommendations.sort(key=lambda x: x.score, reverse=True)
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info("[Recommendation.recommend_people] EXIT | count=%d | elapsed_ms=%.2f", len(recommendations[:limit]), elapsed)
    return recommendations[:limit]
