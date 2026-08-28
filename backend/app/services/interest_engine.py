"""
services/interest_engine.py
============================
Core Interest Graph engine.

Responsibilities:
  - Build and maintain the in-memory NetworkX graph (simulates Neo4j for POC)
  - Compute user interest vectors (pure Python / numpy)
  - Cosine similarity between vectors (pure Python math — NO LLM)
  - Edge weight calculation (pure Python)
  - Graph neighbourhood traversal

CRITICAL CONSTRAINT:
  All mathematical operations in this module are pure Python.
  LLMs are NEVER called here. See nvidia_nim.py for the only LLM touch-points.
"""

import json
import logging
import math
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.entities import (
    Club,
    Domain,
    Event,
    Interest,
    Interaction,
    Post,
    User,
    user_interest_table,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level graph (singleton — rebuilt nightly in production)
# ---------------------------------------------------------------------------
_graph: nx.DiGraph = nx.DiGraph()
_graph_built_at: Optional[datetime] = None

logger.info("[InterestEngine] Module loaded | graph initialised as empty DiGraph")


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

async def build_graph(session: AsyncSession) -> nx.DiGraph:
    """
    Build the in-memory NetworkX interest graph from database state.

    Node types: user, interest, domain, club, business, event, post
    Edge types:
        HAS_INTEREST    user → interest
        MEMBER_OF       user → club
        FOLLOWS         user → user
        ENGAGED_WITH    user → post|club|business|event
        SIMILAR_TO      interest → interest  (co-occurrence)

    Edge weight formula (Section 3 of design doc):
        edge_weight = (alpha * explicit_base)
                    + (beta  * implicit_score * trust_multiplier)
                    + (gamma * recency_factor)

    Args:
        session: Active SQLAlchemy async session

    Returns:
        nx.DiGraph with all nodes and edges populated
    """
    global _graph, _graph_built_at

    logger.info("[InterestEngine.build_graph] ENTER | building full interest graph from DB")
    start_ts = time.perf_counter()

    g = nx.DiGraph()

    # ------------------------------------------------------------------
    # 1. Domain nodes
    # ------------------------------------------------------------------
    logger.info("[InterestEngine.build_graph] Step1: Loading domains")
    domains_result = await session.execute(select(Domain))
    domains = domains_result.scalars().all()
    for domain in domains:
        node_id = f"domain_{domain.id}"
        g.add_node(node_id, label=domain.name, node_type="domain", entity_id=domain.id)
        logger.debug(
            "[InterestEngine.build_graph] Domain node added | node_id=%s | name=%s",
            node_id,
            domain.name,
        )
    logger.info("[InterestEngine.build_graph] Step1 done | domain_nodes=%d", len(domains))

    # ------------------------------------------------------------------
    # 2. Interest nodes + SIMILAR_TO edges (co-occurrence)
    # ------------------------------------------------------------------
    logger.info("[InterestEngine.build_graph] Step2: Loading interests")
    interests_result = await session.execute(select(Interest))
    interests = interests_result.scalars().all()
    interest_id_map: Dict[int, Interest] = {i.id: i for i in interests}

    for interest in interests:
        node_id = f"interest_{interest.id}"
        domain_node_id = f"domain_{interest.domain_id}"
        g.add_node(
            node_id,
            label=interest.name,
            node_type="interest",
            entity_id=interest.id,
            domain_id=interest.domain_id,
        )
        # Interest → Domain edge (HAS_DOMAIN)
        g.add_edge(node_id, domain_node_id, edge_type="HAS_DOMAIN", weight=1.0)

        # SIMILAR_TO edges from co-occurrence (stored as JSON list of IDs)
        if interest.co_occurrence_ids:
            try:
                co_ids = json.loads(interest.co_occurrence_ids)
                logger.debug(
                    "[InterestEngine.build_graph] Interest '%s' co-occurrence ids=%s",
                    interest.name,
                    co_ids,
                )
                for co_id in co_ids:
                    co_node_id = f"interest_{co_id}"
                    # Co-occurrence weight = 0.5 by default (symmetric)
                    co_weight = 0.5
                    g.add_edge(
                        node_id,
                        co_node_id,
                        edge_type="SIMILAR_TO",
                        weight=co_weight,
                    )
                    logger.debug(
                        "[InterestEngine.build_graph] SIMILAR_TO edge | %s → %s | weight=%.2f",
                        node_id,
                        co_node_id,
                        co_weight,
                    )
            except json.JSONDecodeError as e:
                logger.warning(
                    "[InterestEngine.build_graph] Failed to parse co_occurrence_ids for "
                    "interest_id=%d | error=%s",
                    interest.id,
                    e,
                )

    logger.info("[InterestEngine.build_graph] Step2 done | interest_nodes=%d", len(interests))

    # ------------------------------------------------------------------
    # 3. User nodes + HAS_INTEREST edges
    # ------------------------------------------------------------------
    logger.info("[InterestEngine.build_graph] Step3: Loading users")
    users_result = await session.execute(
        select(User)
        .options(selectinload(User.interests))
        .where(User.is_active == True)
    )
    users = users_result.scalars().all()

    for user in users:
        node_id = f"user_{user.id}"
        g.add_node(
            node_id,
            label=user.display_name,
            node_type="user",
            entity_id=user.id,
            trust_score=user.trust_score,
            is_verified=user.is_verified,
        )

        # HAS_INTEREST edges (explicit — from onboarding)
        for interest in user.interests:
            interest_node_id = f"interest_{interest.id}"
            # Explicit edge: alpha * explicit_base (base = 1.0 for onboarding)
            explicit_weight = _compute_edge_weight(
                explicit_base=1.0,
                implicit_score=0.0,
                trust_multiplier=user.trust_score,
                days_since_last_interaction=0.0,  # onboarding is instant
                signal_type="explicit",
            )
            g.add_edge(
                node_id,
                interest_node_id,
                edge_type="HAS_INTEREST",
                weight=explicit_weight,
                source="onboarding",
            )
            logger.debug(
                "[InterestEngine.build_graph] HAS_INTEREST edge | user_%d → interest_%d | "
                "weight=%.4f | interest='%s'",
                user.id,
                interest.id,
                explicit_weight,
                interest.name,
            )

    logger.info("[InterestEngine.build_graph] Step3 done | user_nodes=%d", len(users))

    # ------------------------------------------------------------------
    # 4. Interaction edges (ENGAGED_WITH) — from DB interactions table
    # ------------------------------------------------------------------
    logger.info("[InterestEngine.build_graph] Step4: Loading interactions for graph edges")
    interactions_result = await session.execute(select(Interaction))
    interactions = interactions_result.scalars().all()

    for interaction in interactions:
        user_node_id = f"user_{interaction.user_id}"
        entity_node_id = f"{interaction.entity_type}_{interaction.entity_id}"

        days_since = _compute_days_since(interaction.created_at)
        effective_weight = _compute_edge_weight(
            explicit_base=0.0,
            implicit_score=interaction.raw_weight,
            trust_multiplier=interaction.trust_weighted / max(interaction.raw_weight, 0.01),
            days_since_last_interaction=days_since,
            signal_type="implicit",
        )

        # Add entity node if not present (lazy creation for POC)
        if entity_node_id not in g:
            g.add_node(
                entity_node_id,
                node_type=interaction.entity_type,
                entity_id=interaction.entity_id,
            )

        # Accumulate weight if edge already exists
        if g.has_edge(user_node_id, entity_node_id):
            existing_weight = g[user_node_id][entity_node_id].get("weight", 0.0)
            new_weight = min(existing_weight + effective_weight * 0.5, 1.0)
            g[user_node_id][entity_node_id]["weight"] = new_weight
            logger.debug(
                "[InterestEngine.build_graph] ENGAGED_WITH edge updated | %s → %s | "
                "old_weight=%.4f | delta=%.4f | new_weight=%.4f",
                user_node_id,
                entity_node_id,
                existing_weight,
                effective_weight * 0.5,
                new_weight,
            )
        else:
            g.add_edge(
                user_node_id,
                entity_node_id,
                edge_type="ENGAGED_WITH",
                interaction_type=interaction.interaction_type,
                weight=effective_weight,
            )
            logger.debug(
                "[InterestEngine.build_graph] ENGAGED_WITH edge added | %s → %s | "
                "interaction_type='%s' | days_since=%.1f | weight=%.4f",
                user_node_id,
                entity_node_id,
                interaction.interaction_type,
                days_since,
                effective_weight,
            )

    logger.info(
        "[InterestEngine.build_graph] Step4 done | interaction_edges=%d", len(interactions)
    )

    elapsed_ms = (time.perf_counter() - start_ts) * 1000
    logger.info(
        "[InterestEngine.build_graph] EXIT | nodes=%d | edges=%d | elapsed_ms=%.2f",
        g.number_of_nodes(),
        g.number_of_edges(),
        elapsed_ms,
    )

    _graph = g
    _graph_built_at = datetime.utcnow()
    return g


def get_graph() -> nx.DiGraph:
    """Return the current in-memory graph."""
    logger.debug(
        "[InterestEngine.get_graph] Returning graph | nodes=%d | edges=%d | built_at=%s",
        _graph.number_of_nodes(),
        _graph.number_of_edges(),
        _graph_built_at,
    )
    return _graph


# ---------------------------------------------------------------------------
# Edge weight calculation (PURE PYTHON)
# ---------------------------------------------------------------------------

def _compute_edge_weight(
    explicit_base: float,
    implicit_score: float,
    trust_multiplier: float,
    days_since_last_interaction: float,
    signal_type: str = "implicit",
) -> float:
    """
    Compute edge weight from the design document formula (Section 3):

        edge_weight = (alpha * explicit_base)
                    + (beta  * implicit_score * trust_multiplier)
                    + (gamma * recency_factor)

        recency_factor = exp(-lambda * days_since_last_interaction)

    Args:
        explicit_base:              Base weight for explicit signals (0-1)
        implicit_score:             Signal strength for implicit interactions
        trust_multiplier:           Acting user's trust score (0-1)
        days_since_last_interaction: Time elapsed since interaction
        signal_type:                "explicit" | "implicit" | "medium"

    Returns:
        float in [0, 1]
    """
    logger.debug(
        "[InterestEngine._compute_edge_weight] ENTER | explicit_base=%.4f | "
        "implicit_score=%.4f | trust_multiplier=%.4f | days_since=%.2f | signal_type='%s'",
        explicit_base,
        implicit_score,
        trust_multiplier,
        days_since_last_interaction,
        signal_type,
    )

    alpha = settings.EDGE_WEIGHT_ALPHA  # 0.5
    beta = settings.EDGE_WEIGHT_BETA    # 0.3
    gamma = settings.EDGE_WEIGHT_GAMMA  # 0.2

    # Choose decay lambda based on signal type
    if signal_type == "explicit":
        lambda_val = settings.DECAY_LAMBDA_EXPLICIT
    elif signal_type == "medium":
        lambda_val = settings.DECAY_LAMBDA_MEDIUM
    else:
        lambda_val = settings.DECAY_LAMBDA_IMPLICIT

    logger.debug(
        "[InterestEngine._compute_edge_weight] Params | alpha=%.2f | beta=%.2f | "
        "gamma=%.2f | lambda=%.4f",
        alpha,
        beta,
        gamma,
        lambda_val,
    )

    # Step 1: Recency factor — exp(-lambda * days)
    recency_factor = math.exp(-lambda_val * days_since_last_interaction)
    logger.debug(
        "[InterestEngine._compute_edge_weight] Step1: recency_factor = "
        "exp(-%.4f * %.2f) = exp(%.4f) = %.6f",
        lambda_val,
        days_since_last_interaction,
        -lambda_val * days_since_last_interaction,
        recency_factor,
    )

    # Step 2: Trust-adjusted implicit component
    trust_adjusted_implicit = implicit_score * trust_multiplier
    logger.debug(
        "[InterestEngine._compute_edge_weight] Step2: trust_adjusted_implicit = "
        "%.4f * %.4f = %.6f",
        implicit_score,
        trust_multiplier,
        trust_adjusted_implicit,
    )

    # Step 3: Combine components
    edge_weight = (
        (alpha * explicit_base) +
        (beta * trust_adjusted_implicit) +
        (gamma * recency_factor)
    )
    logger.debug(
        "[InterestEngine._compute_edge_weight] Step3: edge_weight = "
        "(%.2f * %.4f) + (%.2f * %.6f) + (%.2f * %.6f) = %.4f + %.4f + %.4f = %.6f",
        alpha, explicit_base,
        beta, trust_adjusted_implicit,
        gamma, recency_factor,
        alpha * explicit_base,
        beta * trust_adjusted_implicit,
        gamma * recency_factor,
        edge_weight,
    )

    # Step 4: Clamp to [0, 1]
    edge_weight_clamped = max(0.0, min(1.0, edge_weight))
    if edge_weight_clamped != edge_weight:
        logger.debug(
            "[InterestEngine._compute_edge_weight] Step4: clamped %.6f → %.6f",
            edge_weight,
            edge_weight_clamped,
        )

    logger.debug(
        "[InterestEngine._compute_edge_weight] EXIT | edge_weight=%.6f", edge_weight_clamped
    )
    return round(edge_weight_clamped, 6)


def _compute_days_since(dt: Optional[datetime]) -> float:
    """Compute days elapsed since a datetime (returns 0 if None)."""
    if dt is None:
        return 0.0
    delta = datetime.utcnow() - dt
    days = delta.total_seconds() / 86400.0
    logger.debug(
        "[InterestEngine._compute_days_since] dt=%s | now=%s | days=%.4f",
        dt.isoformat(),
        datetime.utcnow().isoformat(),
        days,
    )
    return max(0.0, days)


# ---------------------------------------------------------------------------
# Interest vector operations (PURE PYTHON + NUMPY)
# ---------------------------------------------------------------------------

def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two interest vectors.

    Formula (pure Python — NO LLM):
        cosine_sim = dot(a, b) / (|a| * |b| + epsilon)

    Args:
        vec_a: First vector (user interest vector)
        vec_b: Second vector (entity interest vector)

    Returns:
        float in [-1, 1]  (clipped to [0, 1] for ranking)
    """
    logger.debug(
        "[InterestEngine.compute_cosine_similarity] ENTER | len(vec_a)=%d | len(vec_b)=%d",
        len(vec_a),
        len(vec_b),
    )

    if not vec_a or not vec_b:
        logger.debug(
            "[InterestEngine.compute_cosine_similarity] EXIT | empty vector | returning 0.0"
        )
        return 0.0

    # Ensure same length (pad shorter with zeros)
    max_len = max(len(vec_a), len(vec_b))
    a = vec_a + [0.0] * (max_len - len(vec_a))
    b = vec_b + [0.0] * (max_len - len(vec_b))

    # Step 1: Dot product
    dot_product = sum(ai * bi for ai, bi in zip(a, b))
    logger.debug(
        "[InterestEngine.compute_cosine_similarity] Step1: dot_product = sum(a*b) = %.6f",
        dot_product,
    )

    # Step 2: Magnitudes
    mag_a = math.sqrt(sum(ai ** 2 for ai in a))
    mag_b = math.sqrt(sum(bi ** 2 for bi in b))
    logger.debug(
        "[InterestEngine.compute_cosine_similarity] Step2: |a|=%.6f | |b|=%.6f",
        mag_a,
        mag_b,
    )

    # Step 3: Similarity (with epsilon to prevent div/0)
    epsilon = 1e-9
    similarity = dot_product / (mag_a * mag_b + epsilon)
    logger.debug(
        "[InterestEngine.compute_cosine_similarity] Step3: similarity = %.6f / (%.6f * %.6f + %.0e) = %.6f",
        dot_product,
        mag_a,
        mag_b,
        epsilon,
        similarity,
    )

    # Step 4: Clip to [0, 1]
    clipped = max(0.0, min(1.0, similarity))
    logger.debug(
        "[InterestEngine.compute_cosine_similarity] EXIT | similarity=%.6f", clipped
    )
    return clipped


def build_entity_interest_vector(
    interest_ids: List[int],
    total_interests: int,
    weights: Optional[List[float]] = None,
) -> List[float]:
    """
    Build a one-hot (or weighted) interest vector for an entity.

    Args:
        interest_ids:    List of interest IDs associated with the entity
        total_interests: Total number of interests in the taxonomy
        weights:         Optional weight per interest (defaults to 1.0)

    Returns:
        Float list of length total_interests
    """
    logger.debug(
        "[InterestEngine.build_entity_interest_vector] ENTER | "
        "interest_ids=%s | total_interests=%d | weighted=%s",
        interest_ids,
        total_interests,
        weights is not None,
    )

    vector = [0.0] * total_interests
    for idx, iid in enumerate(interest_ids):
        # interest_id is 1-based; vector index = iid - 1
        vec_idx = iid - 1
        if 0 <= vec_idx < total_interests:
            w = weights[idx] if (weights and idx < len(weights)) else 1.0
            vector[vec_idx] = w
            logger.debug(
                "[InterestEngine.build_entity_interest_vector] Set | interest_id=%d | "
                "vec_idx=%d | weight=%.4f",
                iid,
                vec_idx,
                w,
            )

    logger.debug(
        "[InterestEngine.build_entity_interest_vector] EXIT | "
        "non_zero_dims=%d | vector_len=%d",
        sum(1 for v in vector if v > 0),
        len(vector),
    )
    return vector


def update_user_interest_vector_from_interaction(
    current_vector: List[float],
    interaction_interest_ids: List[int],
    interaction_weight: float,
    is_long_term: bool,
) -> List[float]:
    """
    Update a user's interest vector based on a new interaction.

    For long-term vector:  nudge by (interaction_weight * 0.1)  — conservative
    For short-term session: nudge by (interaction_weight * 0.5)  — responsive

    Args:
        current_vector:             Existing interest vector
        interaction_interest_ids:   Interest IDs from the interacted entity
        interaction_weight:         Effective weight of the interaction
        is_long_term:               True = long-term vector, False = session vector

    Returns:
        Updated vector (same length)
    """
    nudge_factor = 0.10 if is_long_term else 0.50
    logger.debug(
        "[InterestEngine.update_user_interest_vector_from_interaction] ENTER | "
        "vec_len=%d | interest_ids=%s | interaction_weight=%.4f | "
        "is_long_term=%s | nudge_factor=%.2f",
        len(current_vector),
        interaction_interest_ids,
        interaction_weight,
        is_long_term,
        nudge_factor,
    )

    updated = list(current_vector)
    for iid in interaction_interest_ids:
        vec_idx = iid - 1
        if 0 <= vec_idx < len(updated):
            old_val = updated[vec_idx]
            nudge = interaction_weight * nudge_factor
            new_val = min(1.0, old_val + nudge)
            updated[vec_idx] = new_val
            logger.debug(
                "[InterestEngine.update_user_interest_vector_from_interaction] "
                "interest_id=%d | vec_idx=%d | old=%.4f | nudge=%.4f | new=%.4f",
                iid,
                vec_idx,
                old_val,
                nudge,
                new_val,
            )

    logger.debug(
        "[InterestEngine.update_user_interest_vector_from_interaction] EXIT | "
        "changed_dims=%d",
        sum(1 for a, b in zip(current_vector, updated) if a != b),
    )
    return updated


# ---------------------------------------------------------------------------
# Graph traversal
# ---------------------------------------------------------------------------

def get_user_graph_neighborhood(
    user_id: int,
    max_hops: int = 2,
) -> Tuple[List[dict], List[dict]]:
    """
    Return graph nodes and edges within `max_hops` of a user node.

    Args:
        user_id:  User ID to center the traversal on
        max_hops: Maximum edge hops from the user node

    Returns:
        (nodes, edges) lists of dicts for API response
    """
    logger.info(
        "[InterestEngine.get_user_graph_neighborhood] ENTER | user_id=%d | max_hops=%d",
        user_id,
        max_hops,
    )
    g = get_graph()
    user_node = f"user_{user_id}"

    if user_node not in g:
        logger.warning(
            "[InterestEngine.get_user_graph_neighborhood] User node '%s' not found in graph",
            user_node,
        )
        return [], []

    # BFS up to max_hops
    logger.debug(
        "[InterestEngine.get_user_graph_neighborhood] Running BFS | source=%s | depth=%d",
        user_node,
        max_hops,
    )
    reachable = nx.single_source_shortest_path_length(g, user_node, cutoff=max_hops)
    logger.debug(
        "[InterestEngine.get_user_graph_neighborhood] BFS complete | reachable_nodes=%d",
        len(reachable),
    )

    # Build node list
    nodes = []
    for node_id in reachable:
        node_data = g.nodes[node_id]
        nodes.append({
            "id": node_id,
            "label": node_data.get("label", node_id),
            "node_type": node_data.get("node_type", "unknown"),
            "trust_score": node_data.get("trust_score"),
            "properties": {k: v for k, v in node_data.items()
                          if k not in ("label", "node_type", "trust_score")},
        })

    # Build edge list (only edges between reachable nodes)
    node_set = set(reachable.keys())
    edges = []
    for src, tgt, edge_data in g.edges(data=True):
        if src in node_set and tgt in node_set:
            edges.append({
                "source": src,
                "target": tgt,
                "edge_type": edge_data.get("edge_type", "UNKNOWN"),
                "weight": edge_data.get("weight", 0.0),
                "properties": {k: v for k, v in edge_data.items()
                               if k not in ("edge_type", "weight")},
            })

    logger.info(
        "[InterestEngine.get_user_graph_neighborhood] EXIT | nodes=%d | edges=%d",
        len(nodes),
        len(edges),
    )
    return nodes, edges


def get_two_hop_interests(user_id: int) -> List[int]:
    """
    Get interest IDs reachable within 2 hops from user (for exploration / anti-bubble).

    Implements Section 5 of design doc:
    "graph-based 2-hop exploration — surface interests connected to the user's
     interests but not directly selected by them"

    Args:
        user_id: User ID

    Returns:
        List of interest_ids not directly connected to user but 2 hops away
    """
    logger.info(
        "[InterestEngine.get_two_hop_interests] ENTER | user_id=%d", user_id
    )
    g = get_graph()
    user_node = f"user_{user_id}"

    if user_node not in g:
        logger.warning(
            "[InterestEngine.get_two_hop_interests] user_node='%s' not in graph", user_node
        )
        return []

    # Direct interests (1-hop)
    direct_interests = {
        n for n in g.successors(user_node)
        if n.startswith("interest_")
    }
    logger.debug(
        "[InterestEngine.get_two_hop_interests] Direct interests: %s", direct_interests
    )

    # 2-hop interests (neighbours of neighbours)
    two_hop_interests = set()
    for interest_node in direct_interests:
        for neighbour in g.successors(interest_node):
            if neighbour.startswith("interest_") and neighbour not in direct_interests:
                two_hop_interests.add(neighbour)

    # Extract IDs
    two_hop_ids = [
        int(n.split("_")[1]) for n in two_hop_interests
    ]
    logger.info(
        "[InterestEngine.get_two_hop_interests] EXIT | direct=%d | two_hop=%d | ids=%s",
        len(direct_interests),
        len(two_hop_ids),
        two_hop_ids,
    )
    return two_hop_ids
