"""
db/seed.py
==========
Seeds the database with a realistic POC dataset:
  - 5 domains  →  15+ interests
  - 5 users with varied interest profiles
  - 3 clubs
  - 3 businesses
  - 3 events
  - 10 posts (community + business)
  - 20+ interactions to prime the graph

Called automatically on app startup in DEBUG mode if the DB is empty.
"""

import json
import logging
import math
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db_context
from app.models.entities import (
    Business,
    Club,
    Domain,
    Event,
    Interaction,
    Interest,
    Post,
    User,
    business_interest_table,
    club_interest_table,
    event_interest_table,
    post_interest_table,
    user_club_table,
    user_interest_table,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy seed data
# ---------------------------------------------------------------------------

DOMAINS = [
    {"name": "Arts & Creativity", "icon": "🎨", "description": "Visual arts, music, writing, design"},
    {"name": "Technology", "icon": "💻", "description": "Software, hardware, AI, data science"},
    {"name": "Sports & Fitness", "icon": "⚽", "description": "Team sports, fitness, outdoor activities"},
    {"name": "Food & Drink", "icon": "🍜", "description": "Cooking, restaurants, cuisine culture"},
    {"name": "Business & Entrepreneurship", "icon": "💼", "description": "Startups, networking, finance"},
]

INTERESTS_BY_DOMAIN = {
    "Arts & Creativity": [
        {"name": "Photography", "description": "Still and moving image capture"},
        {"name": "Street Photography", "description": "Urban documentary photography"},
        {"name": "Urban Sketching", "description": "Drawing city scenes on location"},
        {"name": "Digital Art", "description": "Art created with digital tools"},
    ],
    "Technology": [
        {"name": "Machine Learning", "description": "ML models and algorithms"},
        {"name": "Web Development", "description": "Frontend and backend web apps"},
        {"name": "Data Science", "description": "Data analysis and visualization"},
        {"name": "Open Source", "description": "Contributing to open-source projects"},
    ],
    "Sports & Fitness": [
        {"name": "Running", "description": "Road and trail running"},
        {"name": "Yoga", "description": "Mindful movement and breathwork"},
        {"name": "Cycling", "description": "Road cycling and mountain biking"},
    ],
    "Food & Drink": [
        {"name": "Coffee Culture", "description": "Specialty coffee and brewing"},
        {"name": "Plant-Based Cooking", "description": "Vegan and vegetarian cuisine"},
        {"name": "Restaurant Discovery", "description": "Finding hidden culinary gems"},
    ],
    "Business & Entrepreneurship": [
        {"name": "Startups", "description": "Early-stage company building"},
        {"name": "Social Impact", "description": "Business with purpose"},
    ],
}


# ---------------------------------------------------------------------------
# User seed data
# ---------------------------------------------------------------------------

USERS_SEED = [
    {
        "username": "alice_photo",
        "display_name": "Alice Chen",
        "email": "alice@example.com",
        "bio": "Street photographer and urban explorer. Coffee addict.",
        "location_city": "San Francisco",
        "location_lat": 37.7749,
        "location_lon": -122.4194,
        "user_type": "community",
        "is_verified": True,
        "trust_score": 0.82,
        "interests": ["Photography", "Street Photography", "Coffee Culture"],
    },
    {
        "username": "bob_ml",
        "display_name": "Bob Kumar",
        "email": "bob@example.com",
        "bio": "ML engineer by day, cyclist by evening.",
        "location_city": "San Francisco",
        "location_lat": 37.7849,
        "location_lon": -122.4094,
        "user_type": "community",
        "is_verified": False,
        "trust_score": 0.65,
        "interests": ["Machine Learning", "Data Science", "Cycling"],
    },
    {
        "username": "carla_startup",
        "display_name": "Carla Reyes",
        "email": "carla@example.com",
        "bio": "Founder @ GreenPlate. Passionate about food and impact.",
        "location_city": "Oakland",
        "location_lat": 37.8044,
        "location_lon": -122.2712,
        "user_type": "creator",
        "is_verified": True,
        "trust_score": 0.75,
        "interests": ["Startups", "Social Impact", "Plant-Based Cooking"],
    },
    {
        "username": "dave_code",
        "display_name": "Dave Park",
        "email": "dave@example.com",
        "bio": "Open source contributor. Web dev and coffee enthusiast.",
        "location_city": "San Jose",
        "location_lat": 37.3382,
        "location_lon": -121.8863,
        "user_type": "community",
        "is_verified": False,
        "trust_score": 0.55,
        "interests": ["Web Development", "Open Source", "Coffee Culture"],
    },
    {
        "username": "elena_fit",
        "display_name": "Elena Novak",
        "email": "elena@example.com",
        "bio": "Yoga instructor and runner. Plant-based living.",
        "location_city": "Berkeley",
        "location_lat": 37.8716,
        "location_lon": -122.2727,
        "user_type": "community",
        "is_verified": False,
        "trust_score": 0.70,
        "interests": ["Yoga", "Running", "Plant-Based Cooking"],
    },
]


CLUBS_SEED = [
    {
        "name": "SF Street Photographers",
        "description": "Weekly photo walks across San Francisco neighbourhoods.",
        "location_city": "San Francisco",
        "location_lat": 37.7749,
        "location_lon": -122.4194,
        "member_count": 134,
        "trust_score": 0.78,
        "authority_score": 0.70,
        "interests": ["Photography", "Street Photography", "Urban Sketching"],
    },
    {
        "name": "Bay Area ML Meetup",
        "description": "Monthly talks on machine learning, data, and AI.",
        "location_city": "San Francisco",
        "location_lat": 37.7849,
        "location_lon": -122.4094,
        "member_count": 412,
        "trust_score": 0.85,
        "authority_score": 0.80,
        "interests": ["Machine Learning", "Data Science", "Web Development"],
    },
    {
        "name": "Plant-Based SF",
        "description": "Vegan and vegetarian food lovers exploring the Bay.",
        "location_city": "Oakland",
        "location_lat": 37.8044,
        "location_lon": -122.2712,
        "member_count": 89,
        "trust_score": 0.72,
        "authority_score": 0.65,
        "interests": ["Plant-Based Cooking", "Restaurant Discovery", "Social Impact"],
    },
]

BUSINESSES_SEED = [
    {
        "name": "Aperture Coffee Roasters",
        "description": "Specialty coffee roastery in the Mission District.",
        "location_city": "San Francisco",
        "location_lat": 37.7639,
        "location_lon": -122.4194,
        "website": "https://aperturecoffee.example.com",
        "is_verified": True,
        "trust_score": 0.88,
        "authority_score": 0.75,
        "spam_risk_score": 0.02,
        "months_active": 18,
        "interests": ["Coffee Culture", "Photography"],
    },
    {
        "name": "DataForge Consulting",
        "description": "ML and data engineering consulting for startups.",
        "location_city": "San Francisco",
        "location_lat": 37.7899,
        "location_lon": -122.3994,
        "website": "https://dataforge.example.com",
        "is_verified": True,
        "trust_score": 0.80,
        "authority_score": 0.72,
        "spam_risk_score": 0.05,
        "months_active": 24,
        "interests": ["Machine Learning", "Data Science", "Startups"],
    },
    {
        "name": "Green Plate Kitchen",
        "description": "100% plant-based meal kits delivered weekly.",
        "location_city": "Oakland",
        "location_lat": 37.8100,
        "location_lon": -122.2600,
        "website": "https://greenplate.example.com",
        "is_verified": False,
        "trust_score": 0.60,
        "authority_score": 0.55,
        "spam_risk_score": 0.10,
        "months_active": 6,
        "interests": ["Plant-Based Cooking", "Social Impact", "Restaurant Discovery"],
    },
]

EVENTS_SEED = [
    {
        "title": "Golden Gate Photo Walk",
        "description": "Sunrise photo walk across the Golden Gate Bridge.",
        "location_city": "San Francisco",
        "location_lat": 37.8199,
        "location_lon": -122.4783,
        "starts_at": datetime.utcnow() + timedelta(days=5),
        "ends_at": datetime.utcnow() + timedelta(days=5, hours=3),
        "rsvp_count": 28,
        "attendance_count": 0,
        "interests": ["Photography", "Street Photography"],
    },
    {
        "title": "Bay Area ML Summit 2026",
        "description": "Full-day conference with talks on LLMs, embeddings, and RAG.",
        "location_city": "San Francisco",
        "location_lat": 37.7830,
        "location_lon": -122.4080,
        "starts_at": datetime.utcnow() + timedelta(days=14),
        "ends_at": datetime.utcnow() + timedelta(days=14, hours=8),
        "rsvp_count": 180,
        "attendance_count": 0,
        "interests": ["Machine Learning", "Data Science", "Web Development"],
    },
    {
        "title": "Plant-Based Potluck",
        "description": "Monthly community dinner — bring a dish, share recipes.",
        "location_city": "Oakland",
        "location_lat": 37.8044,
        "location_lon": -122.2712,
        "starts_at": datetime.utcnow() + timedelta(days=7),
        "ends_at": datetime.utcnow() + timedelta(days=7, hours=3),
        "rsvp_count": 42,
        "attendance_count": 0,
        "interests": ["Plant-Based Cooking", "Social Impact"],
    },
]

POSTS_SEED = [
    {
        "title": "Golden hour at Dolores Park",
        "content": "Caught this incredible light at 7am. The fog was rolling in perfectly. Always worth the early wake-up for street photography in SF.",
        "post_type": "community",
        "author": "alice_photo",
        "interests": ["Photography", "Street Photography"],
        "like_count": 45,
        "comment_count": 8,
        "view_count": 320,
    },
    {
        "title": "Why transformers changed everything",
        "content": "Three years after GPT-3, the field has matured enormously. Here's my take on what the attention mechanism really means for practitioners building ML pipelines.",
        "post_type": "community",
        "author": "bob_ml",
        "interests": ["Machine Learning", "Data Science"],
        "like_count": 112,
        "comment_count": 23,
        "view_count": 890,
    },
    {
        "title": "My plant-based ramen recipe",
        "content": "After 3 months of testing, I've finally nailed the perfect plant-based tonkotsu. The secret is kombu + cashew milk. Full recipe in the thread.",
        "post_type": "community",
        "author": "carla_startup",
        "interests": ["Plant-Based Cooking"],
        "like_count": 88,
        "comment_count": 31,
        "view_count": 620,
    },
    {
        "title": "Open source contribution tips for beginners",
        "content": "Started contributing to open source 2 years ago with a tiny doc fix. Here's a practical guide to making your first PR and getting it merged.",
        "post_type": "community",
        "author": "dave_code",
        "interests": ["Web Development", "Open Source"],
        "like_count": 67,
        "comment_count": 15,
        "view_count": 540,
    },
    {
        "title": "Morning yoga flow — 15 minutes",
        "content": "This 15-minute sequence is what I start every day with. No equipment needed. Works great even in a small apartment.",
        "post_type": "community",
        "author": "elena_fit",
        "interests": ["Yoga", "Running"],
        "like_count": 54,
        "comment_count": 12,
        "view_count": 410,
    },
    {
        "title": "New single-origin from Ethiopia ☕",
        "content": "We just received a stunning natural-process Yirgacheffe. Notes of blueberry, jasmine, and dark chocolate. Come try a cup this week.",
        "post_type": "business",
        "author": "alice_photo",
        "interests": ["Coffee Culture"],
        "like_count": 32,
        "comment_count": 7,
        "view_count": 210,
    },
    {
        "title": "Street sketch — Chinatown alley",
        "content": "Quick 20-minute sketch during lunch. Urban sketching forces you to see the city differently. Join us Saturday for the next group walk.",
        "post_type": "community",
        "author": "alice_photo",
        "interests": ["Urban Sketching", "Street Photography"],
        "like_count": 29,
        "comment_count": 5,
        "view_count": 198,
    },
    {
        "title": "Building a feature store from scratch",
        "content": "At DataForge we recently open-sourced our internal feature store. Here's the architecture decision record behind the key design choices.",
        "post_type": "business",
        "author": "bob_ml",
        "interests": ["Machine Learning", "Data Science", "Open Source"],
        "like_count": 78,
        "comment_count": 18,
        "view_count": 670,
    },
    {
        "title": "Running my first half marathon at 35",
        "content": "18 weeks of training. 3 DNFs before the real race. Here's what I actually learned about pacing, nutrition, and mindset.",
        "post_type": "community",
        "author": "elena_fit",
        "interests": ["Running"],
        "like_count": 91,
        "comment_count": 27,
        "view_count": 780,
    },
    {
        "title": "Impact investing 101 for founders",
        "content": "If you're building a mission-driven startup, here's what impact investors actually look for — and how to position your deck.",
        "post_type": "community",
        "author": "carla_startup",
        "interests": ["Startups", "Social Impact"],
        "like_count": 44,
        "comment_count": 11,
        "view_count": 350,
    },
]


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------

async def _is_seeded(session: AsyncSession) -> bool:
    """Return True if the DB already has data."""
    result = await session.execute(select(Domain).limit(1))
    return result.scalar() is not None


async def seed_database() -> None:
    """
    Populate database with POC seed data.
    Idempotent — skips if data already exists.
    """
    logger.info("[Seed] Starting database seeding process")

    async with get_db_context() as session:
        if await _is_seeded(session):
            logger.info("[Seed] Database already seeded — skipping")
            return

        logger.info("[Seed] Database is empty — inserting seed data")

        # ------------------------------------------------------------------
        # 1. Domains
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d domains", len(DOMAINS))
        domain_map: dict[str, Domain] = {}
        for d_data in DOMAINS:
            domain = Domain(**d_data)
            session.add(domain)
            domain_map[d_data["name"]] = domain
        await session.flush()
        logger.info("[Seed] Domains flushed | count=%d", len(domain_map))

        # ------------------------------------------------------------------
        # 2. Interests
        # ------------------------------------------------------------------
        interest_map: dict[str, Interest] = {}
        total_interests = 0
        for domain_name, interests in INTERESTS_BY_DOMAIN.items():
            domain = domain_map[domain_name]
            logger.info(
                "[Seed] Inserting %d interests for domain '%s'",
                len(interests),
                domain_name,
            )
            for i_data in interests:
                interest = Interest(
                    name=i_data["name"],
                    domain_id=domain.id,
                    description=i_data.get("description"),
                )
                session.add(interest)
                interest_map[i_data["name"]] = interest
                total_interests += 1
        await session.flush()
        logger.info("[Seed] Interests flushed | total_count=%d", total_interests)

        # ------------------------------------------------------------------
        # 3. Users
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d users", len(USERS_SEED))
        user_map: dict[str, User] = {}
        for u_data in USERS_SEED:
            interests_for_user = u_data.pop("interests", [])
            user = User(**u_data)

            # Build interest vector: array of length = total_interests, values = explicit weights
            logger.debug(
                "[Seed] Building interest vector for user '%s' | interests=%s",
                user.username,
                interests_for_user,
            )
            vector = [0.0] * total_interests
            for idx, (iname, interest) in enumerate(interest_map.items()):
                if interest.name in interests_for_user:
                    vector[idx] = 1.0
                    logger.debug(
                        "[Seed] User '%s' interest vector | idx=%d | interest='%s' | weight=1.0",
                        user.username,
                        idx,
                        interest.name,
                    )

            user.interest_vector = json.dumps(vector)
            session.add(user)
            user_map[user.username] = user

        await session.flush()

        # Add user-interest associations
        for u_data_original in USERS_SEED:
            # Re-fetch interest names — popped from dict already in the loop above
            pass

        # We'll insert user_interests via the reassociation step
        for u_data in USERS_SEED:
            pass

        logger.info("[Seed] Users flushed | count=%d", len(user_map))

        # Re-seed user interests using raw insert (since we popped from dict in loop)
        user_interest_seeds = {
            "alice_photo": ["Photography", "Street Photography", "Coffee Culture"],
            "bob_ml": ["Machine Learning", "Data Science", "Cycling"],
            "carla_startup": ["Startups", "Social Impact", "Plant-Based Cooking"],
            "dave_code": ["Web Development", "Open Source", "Coffee Culture"],
            "elena_fit": ["Yoga", "Running", "Plant-Based Cooking"],
        }

        for username, int_names in user_interest_seeds.items():
            user = user_map[username]
            for iname in int_names:
                if iname in interest_map:
                    await session.execute(
                        user_interest_table.insert().values(
                            user_id=user.id,
                            interest_id=interest_map[iname].id,
                            weight=1.0,
                            source="onboarding",
                        )
                    )
                    logger.debug(
                        "[Seed] user_interest | user='%s' | interest='%s' | weight=1.0",
                        username,
                        iname,
                    )

        await session.flush()
        logger.info("[Seed] User-interest associations inserted")

        # ------------------------------------------------------------------
        # 4. Clubs
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d clubs", len(CLUBS_SEED))
        club_map: dict[str, Club] = {}
        for c_data in CLUBS_SEED:
            interests_for_club = c_data.pop("interests", [])
            club = Club(**c_data)
            session.add(club)
            await session.flush()

            for iname in interests_for_club:
                if iname in interest_map:
                    await session.execute(
                        club_interest_table.insert().values(
                            club_id=club.id,
                            interest_id=interest_map[iname].id,
                        )
                    )
            club_map[club.name] = club
            logger.debug(
                "[Seed] Club '%s' inserted | id=%d | interests=%s",
                club.name,
                club.id,
                interests_for_club,
            )

        # Add some user → club memberships
        memberships = [
            ("alice_photo", "SF Street Photographers"),
            ("bob_ml", "Bay Area ML Meetup"),
            ("carla_startup", "Plant-Based SF"),
            ("dave_code", "Bay Area ML Meetup"),
            ("elena_fit", "Plant-Based SF"),
        ]
        for username, club_name in memberships:
            if username in user_map and club_name in club_map:
                await session.execute(
                    user_club_table.insert().values(
                        user_id=user_map[username].id,
                        club_id=club_map[club_name].id,
                    )
                )
                logger.debug(
                    "[Seed] Membership | user='%s' → club='%s'", username, club_name
                )

        # ------------------------------------------------------------------
        # 5. Businesses
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d businesses", len(BUSINESSES_SEED))
        for b_data in BUSINESSES_SEED:
            interests_for_biz = b_data.pop("interests", [])
            business = Business(**b_data)
            session.add(business)
            await session.flush()

            for iname in interests_for_biz:
                if iname in interest_map:
                    await session.execute(
                        business_interest_table.insert().values(
                            business_id=business.id,
                            interest_id=interest_map[iname].id,
                        )
                    )
            logger.debug(
                "[Seed] Business '%s' inserted | id=%d", business.name, business.id
            )

        # ------------------------------------------------------------------
        # 6. Events
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d events", len(EVENTS_SEED))
        for e_data in EVENTS_SEED:
            interests_for_event = e_data.pop("interests", [])
            event = Event(**e_data)
            session.add(event)
            await session.flush()

            for iname in interests_for_event:
                if iname in interest_map:
                    await session.execute(
                        event_interest_table.insert().values(
                            event_id=event.id,
                            interest_id=interest_map[iname].id,
                        )
                    )
            logger.debug(
                "[Seed] Event '%s' inserted | id=%d", event.title, event.id
            )

        # ------------------------------------------------------------------
        # 7. Posts
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting %d posts", len(POSTS_SEED))
        post_list: list[Post] = []
        for p_data in POSTS_SEED:
            interests_for_post = p_data.pop("interests", [])
            author_username = p_data.pop("author")
            post = Post(
                author_id=user_map[author_username].id,
                authority_score=_compute_authority_score(
                    p_data.get("like_count", 0),
                    p_data.get("comment_count", 0),
                    p_data.get("view_count", 0),
                    p_data.get("share_count", 0),
                ),
                **p_data,
            )
            session.add(post)
            await session.flush()

            for iname in interests_for_post:
                if iname in interest_map:
                    await session.execute(
                        post_interest_table.insert().values(
                            post_id=post.id,
                            interest_id=interest_map[iname].id,
                            confidence=1.0,
                            tagged_by="manual",
                        )
                    )
            post_list.append(post)
            logger.debug(
                "[Seed] Post id=%d | type='%s' | author='%s'",
                post.id,
                post.post_type,
                author_username,
            )

        # ------------------------------------------------------------------
        # 8. Interactions (synthetic — primes the graph)
        # ------------------------------------------------------------------
        logger.info("[Seed] Inserting synthetic interactions to prime the graph")
        interaction_seeds = [
            ("alice_photo", "post", 2, "like"),      # alice likes ml post
            ("alice_photo", "post", 2, "view"),      # alice views ml post
            ("bob_ml", "post", 1, "like"),           # bob likes photo post
            ("bob_ml", "post", 1, "view"),           # bob views photo post
            ("carla_startup", "post", 4, "share"),   # carla shares open-source
            ("dave_code", "post", 2, "comment"),     # dave comments ml
            ("elena_fit", "post", 5, "like"),        # elena likes yoga
            ("alice_photo", "club", 1, "rsvp"),      # alice rsvps to event
            ("bob_ml", "event", 2, "rsvp"),          # bob rsvps to ml summit
            ("carla_startup", "event", 3, "rsvp"),   # carla rsvps to potluck
        ]

        for username, entity_type, entity_idx, itype in interaction_seeds:
            if username not in user_map:
                continue

            # entity_idx is 1-based index into the appropriate seed list
            if entity_type == "post" and entity_idx <= len(post_list):
                entity_id = post_list[entity_idx - 1].id
            else:
                entity_id = entity_idx  # assume ID matches (close enough for seed)

            user = user_map[username]
            raw_w = _interaction_raw_weight(itype)
            interaction = Interaction(
                user_id=user.id,
                entity_type=entity_type,
                entity_id=entity_id,
                interaction_type=itype,
                raw_weight=raw_w,
                trust_weighted=raw_w * user.trust_score,
                effective_weight=raw_w * user.trust_score,  # no decay for seed data
                created_at=datetime.utcnow() - timedelta(hours=random.randint(1, 72)),
            )
            session.add(interaction)
            logger.debug(
                "[Seed] Interaction | user='%s' | %s %s=%s | raw_weight=%.2f",
                username,
                itype,
                entity_type,
                entity_id,
                raw_w,
            )

        await session.flush()
        logger.info(
            "[Seed] Seeding complete | domains=%d | interests=%d | users=%d | "
            "clubs=%d | events=%d | posts=%d",
            len(DOMAINS),
            total_interests,
            len(user_map),
            len(CLUBS_SEED),
            len(EVENTS_SEED),
            len(post_list),
        )


def _compute_authority_score(
    like_count: int, comment_count: int, view_count: int, share_count: int = 0
) -> float:
    """
    Compute normalised authority score for a post.

    Formula (pure Python):
        engagement_rate = (likes*2 + comments*3 + shares*4) / max(views, 1)
        authority = tanh(engagement_rate * 10)  # squash to [0, 1]

    Args:
        like_count: number of likes
        comment_count: number of comments
        view_count: number of views
        share_count: number of shares

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[Seed._compute_authority_score] ENTER | likes=%d | comments=%d | views=%d | shares=%d",
        like_count,
        comment_count,
        view_count,
        share_count,
    )

    # Step 1: Weighted engagement numerator
    weighted_engagement = (like_count * 2.0) + (comment_count * 3.0) + (share_count * 4.0)
    logger.debug(
        "[Seed._compute_authority_score] Step1: weighted_engagement = "
        "(likes*2) + (comments*3) + (shares*4) = (%.0f*2) + (%.0f*3) + (%.0f*4) = %.2f",
        like_count,
        comment_count,
        share_count,
        weighted_engagement,
    )

    # Step 2: Engagement rate (normalised by views)
    safe_views = max(view_count, 1)
    engagement_rate = weighted_engagement / safe_views
    logger.debug(
        "[Seed._compute_authority_score] Step2: engagement_rate = %.2f / %d = %.4f",
        weighted_engagement,
        safe_views,
        engagement_rate,
    )

    # Step 3: Squash to [0, 1] using tanh
    authority = math.tanh(engagement_rate * 10)
    logger.debug(
        "[Seed._compute_authority_score] Step3: authority = tanh(%.4f * 10) = tanh(%.4f) = %.4f",
        engagement_rate,
        engagement_rate * 10,
        authority,
    )

    logger.debug(
        "[Seed._compute_authority_score] EXIT | authority_score=%.4f", authority
    )
    return round(authority, 4)


def _interaction_raw_weight(interaction_type: str) -> float:
    """
    Map interaction type to raw signal weight.

    Signal strength table (Section 2 of design doc):
        attended      → 1.00 (strong)
        rsvp          → 0.80 (strong)
        contact_click → 0.70 (medium-strong)
        share         → 0.60 (medium)
        comment       → 0.55 (medium)
        save          → 0.45 (medium)
        like          → 0.40 (medium)
        view          → 0.15 (weak)
        skip          → -0.30 (negative)
        report        → -0.80 (strong negative)
    """
    logger.debug(
        "[Seed._interaction_raw_weight] ENTER | interaction_type='%s'", interaction_type
    )
    weight_table = {
        "attended": 1.00,
        "rsvp": 0.80,
        "contact_click": 0.70,
        "share": 0.60,
        "comment": 0.55,
        "save": 0.45,
        "like": 0.40,
        "view": 0.15,
        "skip": -0.30,
        "report": -0.80,
    }
    weight = weight_table.get(interaction_type, 0.10)
    logger.debug(
        "[Seed._interaction_raw_weight] EXIT | interaction_type='%s' | weight=%.2f",
        interaction_type,
        weight,
    )
    return weight
