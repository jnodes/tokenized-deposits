"""
Pytest fixtures for Quest 2 off-chain orchestration platform tests.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.services import audit


@pytest.fixture
def app():
    """Create a fresh FastAPI application for each test."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async test client using httpx."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_audit_log():
    """Clear the audit log before each test."""
    audit.clear_log()
    yield
    audit.clear_log()
