"""
api/recommendations.py
======================
API endpoints for personalized entity recommendations (Clubs, Businesses, Events, People).
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.entities import Interest, User
from app.models.schemas import RecommendationsResponse
from app.services.recommendation import (
    recommend_businesses,
    recommend_clubs,
    recommend_events,
    recommend_people
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("/{user_id}", response_model=RecommendationsResponse)
async def get_user_recommendations(user_id: int, limit: int = 5, db: AsyncSession = Depends(get_db)):
    """
    Get personalized recommendations for a user.
    Returns lists of recommended clubs, businesses, events, and people to connect with.
    """
    logger.info("[API.get_user_recommendations] ENTER | user_id=%d | limit=%d", user_id, limit)
    
    # 1. Fetch user
    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Decode user vector
    user_vec = []
    if user.interest_vector:
        try:
            user_vec = json.loads(user.interest_vector)
        except Exception as e:
            logger.error("[API.get_user_recommendations] Error decoding user vector: %s", e)

    # 3. Get total interests count
    interests_res = await db.execute(select(Interest))
    total_interests = len(interests_res.scalars().all())

    # 4. Generate recommendations (pure Python)
    clubs = await recommend_clubs(db, user, user_vec, total_interests, limit)
    businesses = await recommend_businesses(db, user, user_vec, total_interests, limit)
    events = await recommend_events(db, user, user_vec, total_interests, limit)
    people = await recommend_people(db, user, user_vec, total_interests, limit)

    logger.info(
        "[API.get_user_recommendations] EXIT | clubs=%d | businesses=%d | events=%d | people=%d",
        len(clubs), len(businesses), len(events), len(people)
    )

    return RecommendationsResponse(
        user_id=user_id,
        clubs=clubs,
        businesses=businesses,
        events=events,
        people=people,
        generated_at=datetime.utcnow()
    )
