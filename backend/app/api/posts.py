"""
api/posts.py
============
API endpoints for creating and fetching posts.
Integrates optional NVIDIA NIM LLM for NLP interest tagging.
"""

import logging
import time
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.entities import Interest, Post, User, post_interest_table
from app.models.schemas import PostCreate, PostOut
from app.services.nvidia_nim import extract_interest_tags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.post("", response_model=PostOut, status_code=status.HTTP_201_CREATED)
async def create_post(payload: PostCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new post.
    If interest_ids are not provided and auto_tag=True, calls NVIDIA NIM Llama 3.1
    to extract relevant interests from post content.
    """
    logger.info("[API.create_post] ENTER | author_id=%d | auto_tag=%s", payload.author_id, payload.auto_tag)
    
    # Verify author
    author_result = await db.execute(select(User).where(User.id == payload.author_id))
    author = author_result.scalar_one_or_none()
    if not author:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Author user not found."
        )

    # Construct post
    post = Post(
        title=payload.title,
        content=payload.content,
        media_url=payload.media_url,
        post_type=payload.post_type,
        author_id=payload.author_id,
        club_id=payload.club_id,
        business_id=payload.business_id,
        event_id=payload.event_id,
        llm_tagged=False
    )
    db.add(post)
    await db.flush() # get post ID

    # Handle interests/tags
    matched_ids = []
    
    if payload.interest_ids is not None:
        # manual tagging
        matched_ids = payload.interest_ids
        for iid in matched_ids:
            await db.execute(
                post_interest_table.insert().values(
                    post_id=post.id,
                    interest_id=iid,
                    confidence=1.0,
                    tagged_by="manual"
                )
            )
            logger.debug("[API.create_post] Manually linked interest ID %d", iid)
    elif payload.auto_tag:
        # Call NVIDIA NIM
        start_llm = time.perf_counter()
        interests_result = await db.execute(select(Interest))
        all_interests = interests_result.scalars().all()
        
        try:
            llm_res = await extract_interest_tags(
                content=post.content,
                available_interests=all_interests,
                post_id=post.id
            )
            matched_ids = llm_res.get("interest_ids", [])
            post.llm_tagged = True
            post.llm_tag_model = llm_res.get("model_used")
            post.llm_tag_latency_ms = llm_res.get("latency_ms")
            
            for iid in matched_ids:
                await db.execute(
                    post_interest_table.insert().values(
                        post_id=post.id,
                        interest_id=iid,
                        confidence=0.9, # estimated confidence
                        tagged_by="llm"
                    )
                )
                logger.debug("[API.create_post] LLM auto-linked interest ID %d", iid)
        except Exception as e:
            logger.error("[API.create_post] Auto-tagging failed: %s. Continuing with empty tags.", e)

    await db.commit()
    
    # Reload post with interests
    post_reloaded_result = await db.execute(
        select(Post)
        .options(selectinload(Post.interests).selectinload(Interest.domain))
        .where(Post.id == post.id)
    )
    post_reloaded = post_reloaded_result.scalar_one()

    logger.info("[API.create_post] EXIT | post_id=%d | linked_interests=%d", post_reloaded.id, len(post_reloaded.interests))
    return post_reloaded


@router.get("", response_model=List[PostOut])
async def list_posts(db: AsyncSession = Depends(get_db)):
    """List all posts."""
    logger.info("[API.list_posts] ENTER")
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.interests).selectinload(Interest.domain))
        .order_by(Post.created_at.desc())
    )
    posts = result.scalars().all()
    logger.info("[API.list_posts] EXIT | count=%d", len(posts))
    return posts
