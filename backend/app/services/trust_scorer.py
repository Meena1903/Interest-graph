"""
services/trust_scorer.py
========================
Trust propagation engine — PageRank-style trust scoring.

Design doc Section 6:
  "trust should not be a static per-account flag. It works better as a propagating
   graph signal, similar in spirit to PageRank: an account's trust is a function of
   both its own history and the trust of the accounts that vouch for it."

CRITICAL CONSTRAINT:
  All calculations are pure Python / math.
  No LLM is called in this module.
"""

import logging
import math
import time
from typing import Dict, List, Optional, Set

import networkx as nx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal strength table (Section 2 of design doc)
# ---------------------------------------------------------------------------

INTERACTION_SIGNAL_STRENGTHS: Dict[str, float] = {
    "attended":      1.00,  # strong
    "rsvp":          0.80,  # strong
    "contact_click": 0.70,  # medium-strong
    "share":         0.60,  # medium
    "comment":       0.55,  # medium
    "save":          0.45,  # medium
    "like":          0.40,  # medium
    "view":          0.15,  # weak
    "skip":         -0.30,  # negative
    "report":        -0.80, # strong negative
}

logger.info(
    "[TrustScorer] Module loaded | signal_strength_table entries=%d",
    len(INTERACTION_SIGNAL_STRENGTHS),
)


# ---------------------------------------------------------------------------
# PageRank-style trust propagation
# ---------------------------------------------------------------------------

def propagate_trust(graph: nx.DiGraph) -> Dict[str, float]:
    """
    Propagate trust scores through the graph using a PageRank-style algorithm.

    Formula (Section 6 of design doc):
        trust[v]_t+1 = (1 - d) + d * sum( trust[u] / out_degree[u]
                                           for u in predecessors(v) )

    where d = TRUST_DAMPING_FACTOR (default 0.85)

    This makes trust compound as the network grows and harder to fake with
    throwaway accounts (those start with low trust and propagate almost nothing).

    Args:
        graph: The in-memory NetworkX DiGraph

    Returns:
        Dict mapping node_id → trust_score (0-1)
    """
    logger.info(
        "[TrustScorer.propagate_trust] ENTER | graph_nodes=%d | graph_edges=%d",
        graph.number_of_nodes(),
        graph.number_of_edges(),
    )
    start_ts = time.perf_counter()

    damping = settings.TRUST_DAMPING_FACTOR
    iterations = settings.TRUST_PROPAGATION_ITERATIONS
    trust_min = settings.TRUST_MIN_SCORE
    trust_max = settings.TRUST_MAX_SCORE

    logger.info(
        "[TrustScorer.propagate_trust] Config | damping=%.3f | iterations=%d | "
        "trust_range=[%.2f, %.2f]",
        damping,
        iterations,
        trust_min,
        trust_max,
    )

    # Initialise: use existing trust scores from node attributes
    trust: Dict[str, float] = {}
    user_nodes = [n for n in graph.nodes if n.startswith("user_")]
    logger.info(
        "[TrustScorer.propagate_trust] User nodes found | count=%d", len(user_nodes)
    )

    for node in user_nodes:
        initial_trust = graph.nodes[node].get("trust_score", 0.5)
        trust[node] = initial_trust
        logger.debug(
            "[TrustScorer.propagate_trust] Init | node=%s | initial_trust=%.4f",
            node,
            initial_trust,
        )

    # Iterative propagation
    for iteration in range(iterations):
        new_trust: Dict[str, float] = {}
        max_delta = 0.0

        for node in user_nodes:
            predecessors = [
                p for p in graph.predecessors(node) if p.startswith("user_")
            ]
            pred_count = len(predecessors)

            if pred_count == 0:
                # Dangling node — keep existing trust
                new_trust[node] = (1.0 - damping) + damping * trust.get(node, 0.5)
                logger.debug(
                    "[TrustScorer.propagate_trust] iter=%d | node=%s | dangling | "
                    "new_trust=%.4f",
                    iteration,
                    node,
                    new_trust[node],
                )
            else:
                # PageRank formula:
                # trust_new = (1 - d) + d * sum(trust[u] / out_degree[u])
                propagated = 0.0
                for pred in predecessors:
                    pred_out_degree = max(graph.out_degree(pred), 1)
                    pred_trust = trust.get(pred, 0.5)
                    contribution = pred_trust / pred_out_degree
                    propagated += contribution
                    logger.debug(
                        "[TrustScorer.propagate_trust] iter=%d | node=%s | "
                        "pred=%s | pred_trust=%.4f | out_degree=%d | "
                        "contribution=%.6f",
                        iteration,
                        node,
                        pred,
                        pred_trust,
                        pred_out_degree,
                        contribution,
                    )

                raw_trust = (1.0 - damping) + damping * propagated
                logger.debug(
                    "[TrustScorer.propagate_trust] iter=%d | node=%s | "
                    "formula: (1-%.3f) + %.3f * %.6f = %.6f + %.6f = %.6f",
                    iteration,
                    node,
                    damping,
                    damping,
                    propagated,
                    1.0 - damping,
                    damping * propagated,
                    raw_trust,
                )
                new_trust[node] = raw_trust

            # Track convergence delta
            delta = abs(new_trust[node] - trust.get(node, 0.5))
            max_delta = max(max_delta, delta)

        trust = new_trust

        logger.info(
            "[TrustScorer.propagate_trust] Iteration %d/%d | max_delta=%.6f",
            iteration + 1,
            iterations,
            max_delta,
        )

        # Early stopping: convergence threshold
        if max_delta < 1e-6:
            logger.info(
                "[TrustScorer.propagate_trust] Converged at iteration %d | max_delta=%.8f",
                iteration + 1,
                max_delta,
            )
            break

    # Normalise to [trust_min, trust_max]
    if trust:
        min_val = min(trust.values())
        max_val = max(trust.values())
        val_range = max_val - min_val if max_val > min_val else 1.0
        logger.info(
            "[TrustScorer.propagate_trust] Normalising | raw_min=%.4f | raw_max=%.4f | "
            "range=%.4f | target=[%.2f, %.2f]",
            min_val,
            max_val,
            val_range,
            trust_min,
            trust_max,
        )

        for node in trust:
            raw = trust[node]
            normalised = trust_min + (raw - min_val) / val_range * (trust_max - trust_min)
            trust[node] = round(normalised, 4)
            logger.debug(
                "[TrustScorer.propagate_trust] Normalised | node=%s | "
                "raw=%.4f → normalised=%.4f",
                node,
                raw,
                trust[node],
            )

    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    logger.info(
        "[TrustScorer.propagate_trust] EXIT | user_trust_scores_computed=%d | "
        "elapsed_ms=%.2f",
        len(trust),
        elapsed_ms,
    )
    return trust


# ---------------------------------------------------------------------------
# Per-entity trust computation
# ---------------------------------------------------------------------------

def compute_user_trust_score(
    is_verified: bool,
    months_active: int,
    report_count: int,
    interaction_count: int,
    spam_flag: bool,
    base_trust: float = 0.50,
) -> float:
    """
    Compute trust score for a user from first-party attributes.

    Formula (pure Python):
        trust = base_trust
              + verification_boost            (if verified)
              + tenure_bonus                  (log scale, capped)
              - report_penalty                (proportional to reports)
              - spam_penalty                  (if spam flag set)
        trust = clamp(trust, trust_min, trust_max)

    Args:
        is_verified:       Whether user has completed ID verification
        months_active:     Account age in months
        report_count:      Number of valid reports against this account
        interaction_count: Total interactions (signals activity)
        spam_flag:         Whether spam detection has flagged this account
        base_trust:        Starting trust score (default 0.5)

    Returns:
        float in [trust_min, trust_max]
    """
    logger.debug(
        "[TrustScorer.compute_user_trust_score] ENTER | is_verified=%s | "
        "months_active=%d | report_count=%d | interaction_count=%d | "
        "spam_flag=%s | base_trust=%.2f",
        is_verified,
        months_active,
        report_count,
        interaction_count,
        spam_flag,
        base_trust,
    )

    trust = base_trust

    # Step 1: Verification boost
    if is_verified:
        boost = settings.VERIFIED_USER_TRUST_BOOST  # 0.15
        trust += boost
        logger.debug(
            "[TrustScorer.compute_user_trust_score] Step1: verified_boost=+%.2f | "
            "trust_after=%.4f",
            boost,
            trust,
        )
    else:
        logger.debug(
            "[TrustScorer.compute_user_trust_score] Step1: not verified | no boost"
        )

    # Step 2: Tenure bonus — log(months + 1) / log(25)  → max ~1 at 2yr
    tenure_bonus = min(math.log(months_active + 1) / math.log(25), 0.20)
    trust += tenure_bonus
    logger.debug(
        "[TrustScorer.compute_user_trust_score] Step2: tenure_bonus = "
        "min(log(%d+1)/log(25), 0.20) = min(%.4f/%.4f, 0.20) = %.4f | trust_after=%.4f",
        months_active,
        math.log(months_active + 1),
        math.log(25),
        tenure_bonus,
        trust,
    )

    # Step 3: Activity bonus — log(interactions + 1) / log(1000)  → max 0.10
    activity_bonus = min(math.log(interaction_count + 1) / math.log(1000), 0.10)
    trust += activity_bonus
    logger.debug(
        "[TrustScorer.compute_user_trust_score] Step3: activity_bonus = "
        "min(log(%d+1)/log(1000), 0.10) = %.4f | trust_after=%.4f",
        interaction_count,
        activity_bonus,
        trust,
    )

    # Step 4: Report penalty — each report deducts proportionally
    if report_count > 0:
        # Penalty = 0.05 per report, saturating at 0.30
        report_penalty = min(report_count * 0.05, 0.30)
        trust -= report_penalty
        logger.debug(
            "[TrustScorer.compute_user_trust_score] Step4: report_penalty = "
            "min(%d * 0.05, 0.30) = %.4f | trust_after=%.4f",
            report_count,
            report_penalty,
            trust,
        )

    # Step 5: Spam flag
    if spam_flag:
        spam_penalty = 0.40
        trust -= spam_penalty
        logger.debug(
            "[TrustScorer.compute_user_trust_score] Step5: spam_penalty=%.2f | "
            "trust_after=%.4f",
            spam_penalty,
            trust,
        )

    # Step 6: Clamp
    trust_min = settings.TRUST_MIN_SCORE
    trust_max = settings.TRUST_MAX_SCORE
    trust_clamped = max(trust_min, min(trust_max, trust))
    logger.debug(
        "[TrustScorer.compute_user_trust_score] Step6: clamp(%.4f, %.2f, %.2f) = %.4f",
        trust,
        trust_min,
        trust_max,
        trust_clamped,
    )

    logger.debug(
        "[TrustScorer.compute_user_trust_score] EXIT | trust_score=%.4f", trust_clamped
    )
    return round(trust_clamped, 4)


def compute_spam_risk_score(
    posting_velocity_per_hour: float,
    avg_engagement_quality: float,
    report_count: int,
    account_age_days: int,
) -> float:
    """
    Compute spam risk score for a business or post.

    Formula (pure Python):
        spam_risk = velocity_component + low_engagement_component + report_component
                  - maturity_discount
        spam_risk = clamp(spam_risk, 0, 1)

    Design doc Section 6:
        "High posting velocity, low engagement quality, repeated reports"
        → trust_multiplier suppressed; may be excluded from commercial budget

    Args:
        posting_velocity_per_hour: Posts per hour over last 24h
        avg_engagement_quality:    Mean engagement quality score (0-1)
        report_count:              Number of reports in last 30 days
        account_age_days:          Account age in days

    Returns:
        float in [0, 1]  where 1 = definitely spam
    """
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] ENTER | velocity=%.2f | "
        "eng_quality=%.2f | reports=%d | age_days=%d",
        posting_velocity_per_hour,
        avg_engagement_quality,
        report_count,
        account_age_days,
    )

    # Step 1: Velocity component
    # Normal posting velocity < 2/hour; spam starts at > 10/hour
    velocity_component = min(posting_velocity_per_hour / 20.0, 0.50)
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] Step1: velocity_component = "
        "min(%.2f/20.0, 0.50) = min(%.4f, 0.50) = %.4f",
        posting_velocity_per_hour,
        posting_velocity_per_hour / 20.0,
        velocity_component,
    )

    # Step 2: Low engagement quality penalty
    # Low quality = high impressions with near-zero engagement
    low_eng_component = max(0.0, (0.3 - avg_engagement_quality) * 0.5)
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] Step2: low_eng_component = "
        "max(0, (0.3 - %.2f) * 0.5) = %.4f",
        avg_engagement_quality,
        low_eng_component,
    )

    # Step 3: Report component
    report_component = min(report_count * 0.08, 0.40)
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] Step3: report_component = "
        "min(%d * 0.08, 0.40) = %.4f",
        report_count,
        report_component,
    )

    # Step 4: Maturity discount (older accounts get benefit of the doubt)
    maturity_discount = min(account_age_days / 365.0 * 0.15, 0.15)
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] Step4: maturity_discount = "
        "min(%d/365.0 * 0.15, 0.15) = %.4f",
        account_age_days,
        maturity_discount,
    )

    # Step 5: Combine
    spam_risk = velocity_component + low_eng_component + report_component - maturity_discount
    spam_risk_clamped = max(0.0, min(1.0, spam_risk))
    logger.debug(
        "[TrustScorer.compute_spam_risk_score] Step5: spam_risk = "
        "%.4f + %.4f + %.4f - %.4f = %.4f → clamped=%.4f",
        velocity_component,
        low_eng_component,
        report_component,
        maturity_discount,
        spam_risk,
        spam_risk_clamped,
    )

    logger.debug(
        "[TrustScorer.compute_spam_risk_score] EXIT | spam_risk=%.4f", spam_risk_clamped
    )
    return round(spam_risk_clamped, 4)
