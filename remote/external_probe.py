"""External probe to check if target IP is reachable."""

import asyncio
import logging
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class ProbeResult(Enum):
    """Result of external probe."""

    REACHABLE = "reachable"
    UNREACHABLE = "unreachable"
    DISABLED = "disabled"


class ExternalProbe:
    """Probe external IP to determine connection status."""

    def __init__(
        self,
        target_ip: str,
        timeout: int = 10,
        enabled: bool = True,
    ):
        self.target_ip = target_ip
        self.timeout = timeout
        self.enabled = enabled and bool(target_ip)

    async def check(self) -> ProbeResult:
        """Check if target IP is reachable."""
        if not self.enabled:
            return ProbeResult.DISABLED

        # Try HTTP probe first (more reliable through NAT)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"http://{self.target_ip}/", follow_redirects=False)
                # Any response means reachable
                logger.debug(
                    f"External probe to {self.target_ip}: reachable (HTTP {response.status_code})"
                )
                return ProbeResult.REACHABLE
        except httpx.HTTPError:
            pass
        except Exception as e:
            logger.debug(f"HTTP probe failed: {e}")

        # Fall back to TCP connect probe on common ports
        for port in [80, 443, 22]:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.target_ip, port),
                    timeout=self.timeout,
                )
                writer.close()
                await writer.wait_closed()
                logger.debug(f"External probe to {self.target_ip}:{port}: reachable")
                return ProbeResult.REACHABLE
            except Exception:
                continue

        logger.info(f"External probe to {self.target_ip}: unreachable")
        return ProbeResult.UNREACHABLE
