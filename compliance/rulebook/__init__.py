"""
Cari Network Rulebook Compliance Module
=========================================
Stubs for Cari Network Rulebook governance compliance checks.
Per the Cari Whitepaper, the Rulebook defines consortium governance rules
that all member banks (including M&T Bank) must adhere to.
"""

from compliance.rulebook.engine import RulebookComplianceEngine, get_rulebook_engine

__all__ = ["RulebookComplianceEngine", "get_rulebook_engine"]
