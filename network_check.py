#!/usr/bin/env python3
"""
Network connectivity check with retry.
Waits for DNS resolution before running reports.
"""

import socket
import time
import logging

logger = logging.getLogger(__name__)

HOSTS_TO_CHECK = ["query1.finance.yahoo.com", "api.notion.com"]
MAX_WAIT = 300  # 5 minutes
CHECK_INTERVAL = 15  # seconds


def wait_for_network(max_wait: int = MAX_WAIT, interval: int = CHECK_INTERVAL) -> bool:
    """Wait until DNS resolution works, up to max_wait seconds.

    Returns True if network is available, False if timed out.
    """
    start = time.time()
    attempt = 0

    while time.time() - start < max_wait:
        attempt += 1
        for host in HOSTS_TO_CHECK:
            try:
                socket.setdefaulttimeout(5)
                socket.getaddrinfo(host, 443)
                if attempt > 1:
                    logger.info(f"Network available after {int(time.time() - start)}s (attempt {attempt})")
                return True
            except (socket.gaierror, socket.timeout, OSError):
                continue

        elapsed = int(time.time() - start)
        logger.warning(f"Network unavailable (attempt {attempt}, {elapsed}s elapsed). Retrying in {interval}s...")
        time.sleep(interval)

    logger.error(f"Network still unavailable after {max_wait}s. Aborting.")
    return False
