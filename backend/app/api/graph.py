"""
api/graph.py
============
API endpoints for visualizing and traversing the interest graph.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.schemas import GraphResponse
from app.services.interest_engine import build_graph, get_user_graph_neighborhood

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["Graph Explorer"])


@router.get("/{user_id}", response_model=GraphResponse)
async def get_graph_explorer(user_id: int, depth: int = 2, db: AsyncSession = Depends(get_db)):
    """
    Get the localized graph neighborhood centered on a user.
    Depth represents the number of edge hops to traverse (default 2).
    """
    logger.info("[API.get_graph_explorer] ENTER | user_id=%d | depth=%d", user_id, depth)

    # 1. Build/sync the in-memory graph from the database
    await build_graph(db)

    # 2. Extract neighborhood centered on user
    nodes, edges = get_user_graph_neighborhood(user_id, max_hops=depth)

    logger.info(
        "[API.get_graph_explorer] EXIT | nodes_returned=%d | edges_returned=%d",
        len(nodes),
        len(edges)
    )

    return GraphResponse(
        user_id=user_id,
        nodes=nodes,
        edges=edges,
        depth=depth,
        node_count=len(nodes),
        edge_count=len(edges)
    )
