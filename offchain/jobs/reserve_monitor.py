"""
Reserve Monitor Background Job
================================
Periodically queries reserve status and populates the ReserveMonitorService
cache so mint pre-checks have up-to-date data.

Production: Wires to on-chain ReserveOracle and Hogan GL (via IBM Z DIH)
to get real reserve balances and attestation freshness.

Run via: python -m offchain.jobs.reserve_monitor
Docker:  command: ["python", "-m", "offchain.jobs.reserve_monitor"]
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("cari.jobs.reserve_monitor")

MONITOR_INTERVAL = int(os.environ.get("MONITOR_INTERVAL_SECONDS", "300"))


async def main() -> None:
    """Main loop: periodically refresh reserve status cache."""
    from offchain.services.reserves import get_reserve_service

    reserve_svc = get_reserve_service()
    logger.info(
        "Reserve monitor started — interval=%ds, waiting for ReserveOracle / Hogan GL integration",
        MONITOR_INTERVAL,
    )

    while True:
        try:
            # TODO: Replace stub values with real data from:
            #   1. On-chain ReserveOracle.getLatestAttestation()
            #   2. Hogan GL query via IBM Z DIH for reserve cash (GL 1010)
            status = await reserve_svc.get_reserve_status(
                total_reserves=0,
                total_supply=0,
                attestation_fresh=False,
                last_attested_at=datetime.now(timezone.utc),
            )
            logger.info("Reserve cache refreshed: %s", status)
        except Exception:
            logger.exception("Reserve monitor tick failed")

        await asyncio.sleep(MONITOR_INTERVAL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(main())
