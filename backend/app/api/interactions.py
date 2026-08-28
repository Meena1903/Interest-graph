"""
api/interactions.py
===================
API endpoints for recording user interactions.
Triggers interest vector updates and trust multiplier application.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.entities import Interaction, Post, User, Interest
from app.models.schemas import InteractionCreate, InteractionOut
from app.services.interest_engine import update_user_interest_vector_from_interaction
from app.db.seed import _interaction_raw_weight

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.post("", response_model=InteractionOut, status_code=status.HTTP_201_CREATED)
async def record_interaction(payload: InteractionCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a new user interaction (view, like, comment, etc.).
    Recalculates user interest vectors near-real-time.
    """
    logger.info(
        "[API.record_interaction] ENTER | user_id=%d | entity=%s/%d | type=%s",
        payload.user_id,
        payload.entity_type,
        payload.entity_id,
        payload.interaction_type
    )

    # 1. Verify user
    user_result = await db.execute(select(User).where(User.id == payload.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Check raw weight
    raw_w = _interaction_raw_weight(payload.interaction_type)
    
    # 3. Calculate trust weighted score
    trust_w = raw_w * user.trust_score

    # 4. Construct interaction
    interaction = Interaction(
        user_id=payload.user_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        interaction_type=payload.interaction_type,
        raw_weight=raw_w,
        trust_weighted=trust_w,
        effective_weight=trust_w, # Recency factor is 1.0 initially (just created)
        session_id=payload.session_id,
        duration_seconds=payload.duration_seconds
    )
    db.add(interaction)

    # 5. Update user analytics stats
    user.interaction_count += 1
    
    # 6. Update user's interest vector if the interacted entity has interests
    interest_ids = []
    if payload.entity_type == "post":
        post_res = await db.execute(
            select(Post).options(selectinload(Post.interests)).where(Post.id == payload.entity_id)
        )
        post = post_res.scalar_one_or_none()
        if post:
            # Increment post view/like count
            if payload.interaction_type == "view":
                post.view_count += 1
            elif payload.interaction_type == "like":
                post.like_count += 1
            elif payload.interaction_type == "comment":
                post.comment_count += 1
            elif payload.interaction_type == "share":
                post.share_count += 1
            elif payload.interaction_type == "save":
                post.save_count += 1
            elif payload.interaction_type == "skip":
                post.skip_count += 1
            
            interest_ids = [i.id for i in post.interests]

    # Recalculate user interest vector if we found interests
    if interest_ids and user.interest_vector:
        try:
            curr_vec = json.loads(user.interest_vector)
            # Update user interest vector in-memory (pure Python)
            updated_vec = update_user_interest_vector_from_interaction(
                current_vector=curr_vec,
                interaction_interest_ids=interest_ids,
                interaction_weight=trust_w,
                is_long_term=True # POC updates long term directly
            )
            user.interest_vector = json.dumps(updated_vec)
            logger.debug("[API.record_interaction] Updated user interest vector.")
        except Exception as e:
            logger.error("[API.record_interaction] Interest vector update failed: %s", e)

    await db.commit()
    await db.refresh(interaction)

    logger.info("[API.record_interaction] EXIT | interaction_id=%d", interaction.id)
    return interaction
