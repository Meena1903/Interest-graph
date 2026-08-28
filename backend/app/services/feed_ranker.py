"""
services/feed_ranker.py
=======================
Multi-factor feed ranking engine — Section 4 of the design document.

Core ranking formula:
    score = w1*Relevance + w2*Trust + w3*Authority
          + w4*Freshness + w5*Proximity + w6*EngagementQuality
          + w7*IntentMatch - SpamRiskPenalty

Post-scoring pipeline:
    1. Compute raw score per post
    2. Apply commercial slot budget (max 20% of feed = business posts)
    3. MMR diversity re-ranking pass (lambda=0.7)
    4. Cold-start fallback if <5 interactions

CRITICAL CONSTRAINT:
  ALL scoring, cosine similarity, decay, MMR, diversity, cold-start calculations
  are pure Python / math. NO LLMs are called in this module.
"""

import json
import logging
import math
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.models.entities import Post, User
from app.services.interest_engine import compute_cosine_similarity

logger = logging.getLogger(__name__)

logger.info("[FeedRanker] Module loaded | ranking formula weights configured")


# ---------------------------------------------------------------------------
# Signal strength weights (used for engagement quality calculation)
# ---------------------------------------------------------------------------

ENGAGEMENT_WEIGHTS: Dict[str, float] = {
    "attended":      1.00,
    "rsvp":          0.80,
    "contact_click": 0.70,
    "share":         0.60,
    "comment":       0.55,
    "save":          0.45,
    "like":          0.40,
    "view":          0.15,
}


# ---------------------------------------------------------------------------
# Core scoring components (all PURE PYTHON)
# ---------------------------------------------------------------------------

def compute_relevance_score(
    user_vector: List[float],
    post_interest_ids: List[int],
    total_interests: int,
) -> float:
    """
    Compute relevance as cosine similarity between user interest vector and post.

    Formula (pure Python — Section 4):
        relevance = cosine_similarity(user_vector, post_vector)

    Args:
        user_vector:       User's stored interest vector (float list)
        post_interest_ids: Interest IDs associated with the post
        total_interests:   Total interests in taxonomy (for vector length)

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[FeedRanker.compute_relevance_score] ENTER | user_vec_len=%d | "
        "post_interest_ids=%s | total_interests=%d",
        len(user_vector),
        post_interest_ids,
        total_interests,
    )

    if not user_vector or not post_interest_ids:
        logger.debug(
            "[FeedRanker.compute_relevance_score] EXIT | no vector or no interests | score=0.0"
        )
        return 0.0

    # Build post interest vector
    post_vector = [0.0] * total_interests
    for iid in post_interest_ids:
        vec_idx = iid - 1
        if 0 <= vec_idx < total_interests:
            post_vector[vec_idx] = 1.0
            logger.debug(
                "[FeedRanker.compute_relevance_score] Post vector | interest_id=%d | "
                "vec_idx=%d | set=1.0",
                iid,
                vec_idx,
            )

    relevance = compute_cosine_similarity(user_vector, post_vector)
    logger.debug(
        "[FeedRanker.compute_relevance_score] EXIT | relevance=%.4f", relevance
    )
    return relevance


def compute_freshness_score(created_at: datetime) -> float:
    """
    Compute content freshness using exponential decay.

    Formula (pure Python — Section 4):
        hours_old = (now - created_at).total_seconds / 3600
        freshness = exp(-lambda_implicit * hours_old / 24)
        (using DECAY_LAMBDA_IMPLICIT so ~1 week half-life)

    Args:
        created_at: Post creation timestamp

    Returns:
        float in (0, 1]  — 1.0 for brand new, approaching 0 for old
    """
    logger.debug(
        "[FeedRanker.compute_freshness_score] ENTER | created_at=%s",
        created_at.isoformat(),
    )

    now = datetime.utcnow()
    delta_seconds = (now - created_at).total_seconds()
    hours_old = max(0.0, delta_seconds / 3600.0)
    days_old = hours_old / 24.0

    lambda_val = settings.DECAY_LAMBDA_IMPLICIT  # 0.10

    freshness = math.exp(-lambda_val * days_old)

    logger.debug(
        "[FeedRanker.compute_freshness_score] Calculation | "
        "now=%s | delta_seconds=%.1f | hours_old=%.2f | days_old=%.4f | "
        "lambda=%.4f | freshness=exp(-%.4f*%.4f)=exp(%.4f)=%.6f",
        now.isoformat(),
        delta_seconds,
        hours_old,
        days_old,
        lambda_val,
        lambda_val,
        days_old,
        -lambda_val * days_old,
        freshness,
    )

    logger.debug(
        "[FeedRanker.compute_freshness_score] EXIT | freshness=%.6f", freshness
    )
    return round(freshness, 6)


def compute_proximity_score(
    user_lat: Optional[float],
    user_lon: Optional[float],
    post_lat: Optional[float],
    post_lon: Optional[float],
    max_km: float = 50.0,
) -> float:
    """
    Compute location proximity score using Haversine distance.

    Formula (pure Python):
        distance_km = haversine(user_loc, post_loc)
        proximity = max(0, 1 - distance_km / max_km)

    Returns 0.5 (neutral) if either location is unknown.

    Args:
        user_lat, user_lon: User coordinates (decimal degrees)
        post_lat, post_lon: Post author/entity coordinates
        max_km:             Maximum distance for non-zero score

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[FeedRanker.compute_proximity_score] ENTER | user_loc=(%s, %s) | "
        "post_loc=(%s, %s) | max_km=%.1f",
        user_lat,
        user_lon,
        post_lat,
        post_lon,
        max_km,
    )

    if any(v is None for v in [user_lat, user_lon, post_lat, post_lon]):
        logger.debug(
            "[FeedRanker.compute_proximity_score] Missing location data | returning neutral 0.5"
        )
        return 0.5

    # Haversine formula (pure Python)
    R = 6371.0  # Earth radius in km
    lat1_rad = math.radians(user_lat)
    lat2_rad = math.radians(post_lat)
    dlat_rad = math.radians(post_lat - user_lat)
    dlon_rad = math.radians(post_lon - user_lon)

    logger.debug(
        "[FeedRanker.compute_proximity_score] Haversine | lat1_rad=%.6f | lat2_rad=%.6f | "
        "dlat_rad=%.6f | dlon_rad=%.6f",
        lat1_rad,
        lat2_rad,
        dlat_rad,
        dlon_rad,
    )

    a = (math.sin(dlat_rad / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon_rad / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance_km = R * c

    logger.debug(
        "[FeedRanker.compute_proximity_score] Haversine result | a=%.8f | c=%.6f | "
        "distance_km=%.4f",
        a,
        c,
        distance_km,
    )

    proximity = max(0.0, 1.0 - distance_km / max_km)
    logger.debug(
        "[FeedRanker.compute_proximity_score] EXIT | distance_km=%.2f | proximity=%.4f",
        distance_km,
        proximity,
    )
    return round(proximity, 4)


def compute_engagement_quality_score(
    like_count: int,
    comment_count: int,
    share_count: int,
    save_count: int,
    view_count: int,
    skip_count: int = 0,
) -> float:
    """
    Compute engagement quality: weighted engagement normalised by views.

    Formula (pure Python — Section 4):
        weighted_eng = likes*0.40 + comments*0.55 + shares*0.60 + saves*0.45 - skips*0.30
        eng_quality  = tanh(weighted_eng / max(views, 1) * 5)

    Uses same weights as ENGAGEMENT_WEIGHTS to stay consistent with signal strength table.

    Args:
        like_count, comment_count, share_count, save_count: Engagement counters
        view_count: Impression count (normalizer)
        skip_count: Skip/pass events (negative signal)

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[FeedRanker.compute_engagement_quality_score] ENTER | likes=%d | comments=%d | "
        "shares=%d | saves=%d | views=%d | skips=%d",
        like_count,
        comment_count,
        share_count,
        save_count,
        view_count,
        skip_count,
    )

    # Step 1: Weighted engagement score
    weighted_eng = (
        like_count * ENGAGEMENT_WEIGHTS["like"] +
        comment_count * ENGAGEMENT_WEIGHTS["comment"] +
        share_count * ENGAGEMENT_WEIGHTS["share"] +
        save_count * ENGAGEMENT_WEIGHTS["save"] -
        skip_count * 0.30  # skip is negative signal
    )
    logger.debug(
        "[FeedRanker.compute_engagement_quality_score] Step1: weighted_eng = "
        "(%d*%.2f) + (%d*%.2f) + (%d*%.2f) + (%d*%.2f) - (%d*0.30) = %.4f",
        like_count, ENGAGEMENT_WEIGHTS["like"],
        comment_count, ENGAGEMENT_WEIGHTS["comment"],
        share_count, ENGAGEMENT_WEIGHTS["share"],
        save_count, ENGAGEMENT_WEIGHTS["save"],
        skip_count,
        weighted_eng,
    )

    # Step 2: Normalise by views
    safe_views = max(view_count, 1)
    eng_rate = max(0.0, weighted_eng) / safe_views
    logger.debug(
        "[FeedRanker.compute_engagement_quality_score] Step2: eng_rate = "
        "max(0, %.4f) / %d = %.6f",
        weighted_eng,
        safe_views,
        eng_rate,
    )

    # Step 3: Squash with tanh
    eng_quality = math.tanh(eng_rate * 5.0)
    logger.debug(
        "[FeedRanker.compute_engagement_quality_score] Step3: eng_quality = "
        "tanh(%.6f * 5.0) = tanh(%.4f) = %.6f",
        eng_rate,
        eng_rate * 5.0,
        eng_quality,
    )

    logger.debug(
        "[FeedRanker.compute_engagement_quality_score] EXIT | eng_quality=%.6f", eng_quality
    )
    return round(eng_quality, 4)


def compute_spam_penalty(spam_risk_score: float) -> float:
    """
    Map spam risk score to ranking penalty.

    Formula (pure Python):
        if spam_risk > 0.7: penalty = HIGH_PENALTY (0.40)
        elif spam_risk > 0.4: penalty = MEDIUM_PENALTY (0.20)
        else: penalty = spam_risk * 0.10  (proportional for low risk)

    Args:
        spam_risk_score: float in [0, 1]

    Returns:
        float penalty to subtract from final score
    """
    logger.debug(
        "[FeedRanker.compute_spam_penalty] ENTER | spam_risk_score=%.4f", spam_risk_score
    )

    high_threshold = 0.70
    medium_threshold = 0.40

    if spam_risk_score > high_threshold:
        penalty = settings.SPAM_RISK_HIGH_PENALTY  # 0.40
        logger.debug(
            "[FeedRanker.compute_spam_penalty] HIGH spam risk | risk=%.4f > %.2f | "
            "penalty=%.4f",
            spam_risk_score,
            high_threshold,
            penalty,
        )
    elif spam_risk_score > medium_threshold:
        penalty = settings.SPAM_RISK_MEDIUM_PENALTY  # 0.20
        logger.debug(
            "[FeedRanker.compute_spam_penalty] MEDIUM spam risk | risk=%.4f > %.2f | "
            "penalty=%.4f",
            spam_risk_score,
            medium_threshold,
            penalty,
        )
    else:
        penalty = spam_risk_score * 0.10
        logger.debug(
            "[FeedRanker.compute_spam_penalty] LOW spam risk | risk=%.4f | "
            "penalty=%.4f*0.10=%.4f",
            spam_risk_score,
            spam_risk_score,
            penalty,
        )

    logger.debug(
        "[FeedRanker.compute_spam_penalty] EXIT | penalty=%.4f", penalty
    )
    return round(penalty, 4)


def compute_final_score(
    relevance: float,
    trust: float,
    authority: float,
    freshness: float,
    proximity: float,
    engagement_quality: float,
    intent_match: float,
    spam_risk_penalty: float,
) -> Tuple[float, str]:
    """
    Compute the composite ranking score.

    Full formula (Section 4 of design doc):
        score = w1*Relevance + w2*Trust + w3*Authority
              + w4*Freshness + w5*Proximity + w6*EngagementQuality
              + w7*IntentMatch - SpamRiskPenalty

    Weights from settings:
        w1 = WEIGHT_RELEVANCE    = 0.30
        w2 = WEIGHT_TRUST        = 0.20
        w3 = WEIGHT_AUTHORITY    = 0.15
        w4 = WEIGHT_FRESHNESS    = 0.15
        w5 = WEIGHT_PROXIMITY    = 0.10
        w6 = WEIGHT_ENGAGEMENT   = 0.05
        w7 = WEIGHT_INTENT       = 0.05

    Args:
        relevance, trust, authority, freshness, proximity,
        engagement_quality, intent_match: Score components (0-1 each)
        spam_risk_penalty: Amount to deduct from final score

    Returns:
        (final_score, formula_string) — score clamped to [0, 1] and human-readable formula
    """
    logger.debug(
        "[FeedRanker.compute_final_score] ENTER | relevance=%.4f | trust=%.4f | "
        "authority=%.4f | freshness=%.4f | proximity=%.4f | engagement=%.4f | "
        "intent=%.4f | spam_penalty=%.4f",
        relevance,
        trust,
        authority,
        freshness,
        proximity,
        engagement_quality,
        intent_match,
        spam_risk_penalty,
    )

    w1 = settings.WEIGHT_RELEVANCE    # 0.30
    w2 = settings.WEIGHT_TRUST        # 0.20
    w3 = settings.WEIGHT_AUTHORITY    # 0.15
    w4 = settings.WEIGHT_FRESHNESS    # 0.15
    w5 = settings.WEIGHT_PROXIMITY    # 0.10
    w6 = settings.WEIGHT_ENGAGEMENT   # 0.05
    w7 = settings.WEIGHT_INTENT       # 0.05

    # Individual contributions
    c_relevance = w1 * relevance
    c_trust = w2 * trust
    c_authority = w3 * authority
    c_freshness = w4 * freshness
    c_proximity = w5 * proximity
    c_engagement = w6 * engagement_quality
    c_intent = w7 * intent_match

    logger.debug(
        "[FeedRanker.compute_final_score] Component contributions | "
        "c_relevance=%.2f*%.4f=%.4f | c_trust=%.2f*%.4f=%.4f | "
        "c_authority=%.2f*%.4f=%.4f | c_freshness=%.2f*%.4f=%.4f | "
        "c_proximity=%.2f*%.4f=%.4f | c_engagement=%.2f*%.4f=%.4f | "
        "c_intent=%.2f*%.4f=%.4f",
        w1, relevance, c_relevance,
        w2, trust, c_trust,
        w3, authority, c_authority,
        w4, freshness, c_freshness,
        w5, proximity, c_proximity,
        w6, engagement_quality, c_engagement,
        w7, intent_match, c_intent,
    )

    weighted_sum = (c_relevance + c_trust + c_authority + c_freshness +
                    c_proximity + c_engagement + c_intent)
    logger.debug(
        "[FeedRanker.compute_final_score] weighted_sum = "
        "%.4f + %.4f + %.4f + %.4f + %.4f + %.4f + %.4f = %.6f",
        c_relevance, c_trust, c_authority, c_freshness,
        c_proximity, c_engagement, c_intent, weighted_sum,
    )

    raw_score = weighted_sum - spam_risk_penalty
    logger.debug(
        "[FeedRanker.compute_final_score] raw_score = %.6f - %.4f = %.6f",
        weighted_sum,
        spam_risk_penalty,
        raw_score,
    )

    final_score = max(0.0, min(1.0, raw_score))
    logger.debug(
        "[FeedRanker.compute_final_score] final_score (clamped) = %.6f", final_score
    )

    formula = (
        f"score = ({w1:.2f}×{relevance:.3f}) + ({w2:.2f}×{trust:.3f}) + "
        f"({w3:.2f}×{authority:.3f}) + ({w4:.2f}×{freshness:.3f}) + "
        f"({w5:.2f}×{proximity:.3f}) + ({w6:.2f}×{engagement_quality:.3f}) + "
        f"({w7:.2f}×{intent_match:.3f}) - {spam_risk_penalty:.3f} = {final_score:.4f}"
    )
    logger.debug("[FeedRanker.compute_final_score] formula='%s'", formula)

    logger.debug("[FeedRanker.compute_final_score] EXIT | final_score=%.6f", final_score)
    return round(final_score, 4), formula


# ---------------------------------------------------------------------------
# MMR Diversity Re-ranking (pure Python)
# ---------------------------------------------------------------------------

def mmr_rerank(
    ranked_items: List[dict],
    lambda_mmr: float,
    top_k: int,
) -> List[dict]:
    """
    Maximal Marginal Relevance (MMR) re-ranking to reduce filter bubbles.

    Formula (pure Python — Section 4):
        mmr_score(d) = lambda * relevance(d)
                     - (1 - lambda) * max_similarity(d, selected_set)

    where max_similarity is the max cosine similarity between d and any
    already-selected document.

    Design doc Section 5:
        "diversity slot budget as a lightweight multi-armed bandit — most slots
         exploit the known-best content, a smaller reserved fraction explores"

    Args:
        ranked_items: List of dicts with keys: 'post_id', 'final_score', 'interest_vector'
        lambda_mmr:   Trade-off (1.0 = pure relevance, 0.0 = pure diversity)
        top_k:        Target number of results after re-ranking

    Returns:
        Re-ordered list with 'diversity_boost' flag added
    """
    logger.info(
        "[FeedRanker.mmr_rerank] ENTER | candidates=%d | lambda=%.2f | top_k=%d",
        len(ranked_items),
        lambda_mmr,
        top_k,
    )

    if not ranked_items:
        logger.info("[FeedRanker.mmr_rerank] EXIT | empty input | returning []")
        return []

    if len(ranked_items) <= top_k:
        logger.info(
            "[FeedRanker.mmr_rerank] EXIT | fewer candidates than top_k | returning all"
        )
        for item in ranked_items:
            item["diversity_boost"] = False
        return ranked_items

    selected = []
    remaining = list(ranked_items)

    for iteration in range(min(top_k, len(remaining))):
        best_item = None
        best_mmr = float("-inf")
        best_diversity = False

        for item in remaining:
            relevance = item.get("final_score", 0.0)
            item_vec = item.get("interest_vector", [])

            # Max similarity to already-selected items
            if not selected:
                max_sim = 0.0
            else:
                similarities = []
                for sel in selected:
                    sel_vec = sel.get("interest_vector", [])
                    sim = compute_cosine_similarity(item_vec, sel_vec)
                    similarities.append(sim)
                    logger.debug(
                        "[FeedRanker.mmr_rerank] iter=%d | item=%s | sel=%s | sim=%.4f",
                        iteration,
                        item.get("post_id"),
                        sel.get("post_id"),
                        sim,
                    )
                max_sim = max(similarities) if similarities else 0.0

            mmr = lambda_mmr * relevance - (1.0 - lambda_mmr) * max_sim
            is_diversity = max_sim > 0.7  # flag if selected mainly for diversity

            logger.debug(
                "[FeedRanker.mmr_rerank] iter=%d | item=%s | relevance=%.4f | "
                "max_sim=%.4f | mmr=%.4f*%.4f - %.4f*%.4f = %.4f",
                iteration,
                item.get("post_id"),
                relevance,
                max_sim,
                lambda_mmr,
                relevance,
                1.0 - lambda_mmr,
                max_sim,
                mmr,
            )

            if mmr > best_mmr:
                best_mmr = mmr
                best_item = item
                best_diversity = is_diversity

        if best_item is not None:
            best_item["diversity_boost"] = best_diversity
            selected.append(best_item)
            remaining.remove(best_item)
            logger.debug(
                "[FeedRanker.mmr_rerank] Selected | iter=%d | item=%s | mmr=%.4f | "
                "diversity_boost=%s",
                iteration,
                best_item.get("post_id"),
                best_mmr,
                best_diversity,
            )

    logger.info(
        "[FeedRanker.mmr_rerank] EXIT | selected=%d | from_candidates=%d",
        len(selected),
        len(ranked_items),
    )
    return selected


# ---------------------------------------------------------------------------
# Commercial slot budget enforcement (Section 4 and 6)
# ---------------------------------------------------------------------------

def apply_slot_budget(
    ranked_items: List[dict],
    commercial_fraction: float,
) -> List[dict]:
    """
    Enforce the commercial content slot budget.

    Design doc Section 4:
        "hard structural rule that prevents commercial content from crowding out
         community content"

    Hard rule: max commercial_fraction of feed can be business/event_promo posts.

    Args:
        ranked_items:         MMR-ranked items with 'post_type' field
        commercial_fraction:  Max fraction of feed for commercial content (0.20)

    Returns:
        Filtered list respecting the slot budget
    """
    logger.info(
        "[FeedRanker.apply_slot_budget] ENTER | total_items=%d | commercial_fraction=%.2f",
        len(ranked_items),
        commercial_fraction,
    )

    if not ranked_items:
        return []

    max_commercial = max(1, int(len(ranked_items) * commercial_fraction))
    logger.info(
        "[FeedRanker.apply_slot_budget] Max commercial slots = max(1, int(%d * %.2f)) = %d",
        len(ranked_items),
        commercial_fraction,
        max_commercial,
    )

    result = []
    commercial_count = 0
    community_count = 0

    for item in ranked_items:
        post_type = item.get("post_type", "community")
        is_commercial = post_type in ("business", "event_promo")

        if is_commercial:
            if commercial_count < max_commercial:
                commercial_count += 1
                result.append(item)
                logger.debug(
                    "[FeedRanker.apply_slot_budget] INCLUDE commercial | "
                    "post_id=%s | commercial_count=%d/%d",
                    item.get("post_id"),
                    commercial_count,
                    max_commercial,
                )
            else:
                logger.debug(
                    "[FeedRanker.apply_slot_budget] SKIP commercial (budget exhausted) | "
                    "post_id=%s",
                    item.get("post_id"),
                )
        else:
            community_count += 1
            result.append(item)
            logger.debug(
                "[FeedRanker.apply_slot_budget] INCLUDE community | post_id=%s | "
                "community_count=%d",
                item.get("post_id"),
                community_count,
            )

    logger.info(
        "[FeedRanker.apply_slot_budget] EXIT | result=%d | community=%d | commercial=%d",
        len(result),
        community_count,
        commercial_count,
    )
    return result


# ---------------------------------------------------------------------------
# Cold-start handling (Section 5)
# ---------------------------------------------------------------------------

def is_cold_start_user(interaction_count: int) -> bool:
    """
    Determine if a user is in cold-start (Section 5).

    Cold start threshold = COLD_START_THRESHOLD (default 5 interactions).

    Args:
        interaction_count: Total recorded interactions for the user

    Returns:
        True if user is cold-start
    """
    threshold = settings.COLD_START_THRESHOLD
    is_cold = interaction_count < threshold
    logger.debug(
        "[FeedRanker.is_cold_start_user] interaction_count=%d | threshold=%d | "
        "is_cold_start=%s",
        interaction_count,
        threshold,
        is_cold,
    )
    return is_cold


def compute_cold_start_score(
    post_authority: float,
    post_freshness: float,
    proximity: float,
    relevance_from_onboarding: float,
) -> float:
    """
    Cold-start ranking score — uses popularity + location + onboarding interests.

    Design doc Section 4 (cold start):
        "fall back to a blend of popularity + location + onboarding interests
         + 'trending near you', with weights shifting toward personalized relevance
         as real interaction data accumulates"

    Formula (pure Python):
        cold_score = 0.30 * popularity(authority)
                   + 0.30 * proximity
                   + 0.25 * relevance_from_onboarding
                   + 0.15 * freshness

    Args:
        post_authority:              Normalised authority/popularity score
        post_freshness:              Freshness score
        proximity:                   Location proximity score
        relevance_from_onboarding:   Cosine similarity using only onboarding interests

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[FeedRanker.compute_cold_start_score] ENTER | authority=%.4f | freshness=%.4f | "
        "proximity=%.4f | onboarding_relevance=%.4f",
        post_authority,
        post_freshness,
        proximity,
        relevance_from_onboarding,
    )

    w_popularity = 0.30
    w_proximity = 0.30
    w_relevance = 0.25
    w_freshness = 0.15

    cold_score = (
        w_popularity * post_authority +
        w_proximity * proximity +
        w_relevance * relevance_from_onboarding +
        w_freshness * post_freshness
    )

    logger.debug(
        "[FeedRanker.compute_cold_start_score] cold_score = "
        "(%0.2f*%.4f) + (%.2f*%.4f) + (%.2f*%.4f) + (%.2f*%.4f) = "
        "%.4f + %.4f + %.4f + %.4f = %.6f",
        w_popularity, post_authority,
        w_proximity, proximity,
        w_relevance, relevance_from_onboarding,
        w_freshness, post_freshness,
        w_popularity * post_authority,
        w_proximity * proximity,
        w_relevance * relevance_from_onboarding,
        w_freshness * post_freshness,
        cold_score,
    )

    cold_score_clamped = max(0.0, min(1.0, cold_score))
    logger.debug(
        "[FeedRanker.compute_cold_start_score] EXIT | cold_score=%.4f", cold_score_clamped
    )
    return round(cold_score_clamped, 4)
