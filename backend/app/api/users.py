"""
api/users.py
============
API endpoints for creating users, fetching profiles, onboarding,
and managing user interest vectors.
"""

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.entities import Interest, User, user_interest_table
from app.models.schemas import UserCreate, UserOut, UserProfile
from app.services.trust_scorer import compute_user_trust_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user with onboarding interests."""
    logger.info("[API.create_user] ENTER | username=%s | email=%s", payload.username, payload.email)
    
    # Check if username or email exists
    existing = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.scalar() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists."
        )

    # Resolve interests
    interests_result = await db.execute(select(Interest))
    all_interests = interests_result.scalars().all()
    interest_map = {i.id: i for i in all_interests}
    
    # Construct user
    user = User(
        username=payload.username,
        display_name=payload.display_name,
        email=payload.email,
        bio=payload.bio,
        location_city=payload.location_city,
        location_lat=payload.location_lat,
        location_lon=payload.location_lon,
        user_type=payload.user_type,
        trust_score=compute_user_trust_score(
            is_verified=False,
            months_active=0,
            report_count=0,
            interaction_count=0,
            spam_flag=False
        )
    )
    db.add(user)
    await db.flush() # get user ID

    # Build interest vector
    total_interests = len(all_interests)
    vector = [0.0] * total_interests
    
    for iid in payload.interest_ids:
        if iid in interest_map:
            # set index iid-1 to 1.0 (onboarding explicit)
            vector[iid - 1] = 1.0
            # insert junction table
            await db.execute(
                user_interest_table.insert().values(
                    user_id=user.id,
                    interest_id=iid,
                    weight=1.0,
                    source="onboarding"
                )
            )
            logger.debug("[API.create_user] Associated explicit interest: %s", interest_map[iid].name)

    user.interest_vector = json.dumps(vector)
    await db.commit()
    await db.refresh(user)

    logger.info("[API.create_user] EXIT | user_id=%d | username=%s", user.id, user.username)
    return user


@router.get("", response_model=List[UserOut])
async def list_users(db: AsyncSession = Depends(get_db)):
    """List all users."""
    logger.info("[API.list_users] ENTER")
    result = await db.execute(select(User).options(selectinload(User.interests)))
    users = result.scalars().all()
    logger.info("[API.list_users] EXIT | count=%d", len(users))
    return users


@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: int, db: AsyncSession = Depends(get_db)):
    """Get full user profile including interest vector values."""
    logger.info("[API.get_user_profile] ENTER | user_id=%d", user_id)
    
    result = await db.execute(
        select(User).options(selectinload(User.interests)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Decode vector
    vector = []
    labels = []
    if user.interest_vector:
        try:
            vector = json.loads(user.interest_vector)
            # Find labels matching index
            interests_result = await db.execute(select(Interest).order_by(Interest.id))
            all_interests = interests_result.scalars().all()
            labels = [i.name for i in all_interests]
        except Exception as e:
            logger.error("[API.get_user_profile] Error loading vector: %s", e)

    profile = UserProfile.model_validate(user)
    profile.interest_vector = vector
    profile.interest_vector_labels = labels

    logger.info("[API.get_user_profile] EXIT | username=%s", user.username)
    return profile
