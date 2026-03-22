"""
Pytest fixtures for Quest 3 compliance tests.
"""

from __future__ import annotations

import pytest

from offchain.services import audit


@pytest.fixture(autouse=True)
def clear_audit_log():
    """Clear the audit log before each test."""
    audit.clear_log()
    yield
    audit.clear_log()
