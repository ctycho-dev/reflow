# app/api/dependencies/db.py
from fastapi import Request


async def get_session(request: Request):
    """
    FastAPI dependency to get a database session.
    Pulls the DatabaseManager from app.state (set in lifespan).
    """
    async with request.app.state.db.session_scope() as session:
        yield session
