"""
api/feed.py
============
Feed generation API route.
Applies pure Python multi-factor scoring, MMR diversity, and commercial slot budgets.
"""

import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.entities import Interest, Post, User
from app.models.schemas import FeedResponse, PostOut, RankedPost, UserOut
from app.services.feed_ranker import (
    compute_cold_start_score,
    compute_engagement_quality_score,
    compute_final_score,
    compute_freshness_score,
    compute_proximity_score,
    compute_relevance_score,
    compute_spam_penalty,
    is_cold_start_user,
    mmr_rerank,
    apply_slot_budget
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["Feed"])


@router.get("/{user_id}", response_model=FeedResponse)
async def get_user_feed(user_id: int, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Generate a personalized feed for a user.
    Uses pure Python scoring, location proximity, trust scores, MMR diversity re-ranking,
    and commercial slot budgeting.
    """
    logger.info("[API.get_user_feed] ENTER | user_id=%d | limit=%d", user_id, limit)
    
    # 1. Fetch user
    user_res = await db.execute(
        select(User).options(selectinload(User.interests)).where(User.id == user_id)
    )
    user = user_res.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 2. Determine cold start
    cold_start = is_cold_start_user(user.interaction_count)
    
    # 3. Load all candidate posts (excluding author's own posts for discovery, or include all for POC)
    # We include all posts for POC so feed has enough content
    posts_res = await db.execute(
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.interests).selectinload(Interest.domain))
        .where(Post.is_hidden == False)
    )
    posts = posts_res.scalars().all()
    
    # Get total count of interests for vector representation
    interests_res = await db.execute(select(Interest))
    total_interests = len(interests_res.scalars().all())

    # Decode user interest vector
    user_vec = []
    if user.interest_vector:
        user_vec = json.loads(user.interest_vector)

    candidates = []
    
    for post in posts:
        # Calculate raw score factors (pure Python math)
        relevance = compute_relevance_score(user_vec, [i.id for i in post.interests], total_interests)
        trust = post.author.trust_score
        
        # Calculate engagement quality
        engagement_quality = compute_engagement_quality_score(
            like_count=post.like_count,
            comment_count=post.comment_count,
            share_count=post.share_count,
            save_count=post.save_count,
            view_count=post.view_count,
            skip_count=post.skip_count
        )
        
        authority = post.authority_score
        freshness = compute_freshness_score(post.created_at)
        
        # Proximity
        proximity = compute_proximity_score(
            user_lat=user.location_lat,
            user_lon=user.location_lon,
            post_lat=post.author.location_lat,
            post_lon=post.author.location_lon
        )
        
        # Intent Match (in POC: co-occurrence of posts shared by follows)
        intent_match = 0.5 # default baseline
        
        # Spam Penalty
        spam_penalty = compute_spam_penalty(post.spam_risk_score)

        # Composite score calculation
        if cold_start:
            final_score = compute_cold_start_score(
                post_authority=authority,
                post_freshness=freshness,
                proximity=proximity,
                relevance_from_onboarding=relevance
            )
            formula_str = f"cold_start = (0.30×{authority:.3f}) + (0.30×{proximity:.3f}) + (0.25×{relevance:.3f}) + (0.15×{freshness:.3f}) = {final_score:.4f}"
        else:
            final_score, formula_str = compute_final_score(
                relevance=relevance,
                trust=trust,
                authority=authority,
                freshness=freshness,
                proximity=proximity,
                engagement_quality=engagement_quality,
                intent_match=intent_match,
                spam_risk_penalty=spam_penalty
            )

        post_out = PostOut.model_validate(post)
        author_out = UserOut.model_validate(post.author)

        # Vector representation of post interests for MMR re-ranking
        post_vec = [0.0] * total_interests
        for i in post.interests:
            if 0 <= i.id - 1 < total_interests:
                post_vec[i.id - 1] = 1.0

        candidates.append({
            "post": post_out,
            "author": author_out,
            "final_score": final_score,
            "relevance": relevance,
            "trust": trust,
            "authority": authority,
            "freshness": freshness,
            "proximity": proximity,
            "engagement_quality": engagement_quality,
            "intent_match": intent_match,
            "spam_risk_penalty": spam_penalty,
            "score_formula": formula_str,
            "interest_vector": post_vec,
            "post_type": post.post_type,
            "post_id": post.id
        })

    # Sort initial ranking
    candidates.sort(key=lambda x: x["final_score"], reverse=True)

    # 4. Apply MMR Diversity Re-ranking (pure Python)
    mmr_res = mmr_rerank(candidates, lambda_mmr=0.7, top_k=limit * 2)

    # 5. Enforce commercial content slot budget (max 20% commercial)
    budgeted_feed = apply_slot_budget(mmr_res, commercial_fraction=0.20)

    # Limit to requested size
    final_feed_items = budgeted_feed[:limit]

    # Convert to schema format
    feed_response_items = []
    for item in final_feed_items:
        feed_response_items.append(
            RankedPost(
                post=item["post"],
                author=item["author"],
                final_score=item["final_score"],
                relevance=item["relevance"],
                trust=item["trust"],
                authority=item["authority"],
                freshness=item["freshness"],
                proximity=item["proximity"],
                engagement_quality=item["engagement_quality"],
                intent_match=item["intent_match"],
                spam_risk_penalty=item["spam_risk_penalty"],
                diversity_boost=item.get("diversity_boost", False),
                score_formula=item["score_formula"]
            )
        )

    logger.info(
        "[API.get_user_feed] EXIT | returned_count=%d | strategy=%s",
        len(feed_response_items),
        "cold_start" if cold_start else "personalized"
    )

    return FeedResponse(
        user_id=user_id,
        is_cold_start=cold_start,
        total_candidates=len(candidates),
        returned_count=len(feed_response_items),
        feed=feed_response_items,
        generated_at=datetime.utcnow(),
        feed_strategy="cold_start" if cold_start else "personalized"
    )
