"""Scheduler - keine internen Jobs mehr.

Die fruehere interne Pipeline (Research/Learning/Full-Pipeline) wurde entfernt.
Automatisierung laeuft extern via n8n (Nightly Generation) + Harvester/Keepa.
setup_tsf_scheduler bleibt als No-op erhalten, damit main.py unveraendert bleibt.
"""

import logging

logger = logging.getLogger(__name__)


def setup_tsf_scheduler():
    """Keine internen Scheduler-Jobs (Automatisierung extern via n8n)."""
    logger.info("T-Shirt Factory: keine internen Scheduler-Jobs (n8n/Harvester extern).")
