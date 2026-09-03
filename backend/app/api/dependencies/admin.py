from fastapi import Depends, HTTPException, status
from loguru import logger

from app.api.dependencies.public import get_current_actor
from app.core.actor import Actor


async def require_admin(actor: Actor = Depends(get_current_actor)) -> Actor:
    if not actor.is_privileged:
        logger.warning(f"Non-privileged actor {actor.log} denied admin access")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return actor
