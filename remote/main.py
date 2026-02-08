# remote/main.py
"""Remote sentinel main entry point."""

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

import uvicorn

from remote.alert_engine import RemoteAlertEngine
from remote.dns_monitor import DnsMonitor
from remote.external_probe import ExternalProbe
from remote.heartbeat_receiver import HeartbeatStore, create_app
from shared.config import EnvConfig, load_remote_config
from shared.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


class RemoteSentinel:
    """Main remote sentinel orchestrator."""

    def __init__(
        self,
        config_path: Path,
        mock_telegram: bool = False,
    ):
        self.config = load_remote_config(config_path)
        self.env = EnvConfig()
        self.mock_telegram = mock_telegram

        # Initialize components
        self.store = HeartbeatStore(
            expected_interval=self.config.heartbeat.expected_interval,
            missed_threshold=self.config.heartbeat.missed_threshold,
        )

        self.probe = ExternalProbe(
            target_ip=self.config.external_probe.target_ip,
            timeout=self.config.external_probe.timeout,
            enabled=self.config.external_probe.enabled,
        )

        self.alert_engine = RemoteAlertEngine()

        self.dns_monitor: DnsMonitor | None = None
        if self.config.dns_monitor.enabled and self.config.dns_monitor.hostname:
            self.dns_monitor = DnsMonitor(
                hostname=self.config.dns_monitor.hostname,
                expected_ip=self.config.dns_monitor.expected_ip,
            )

        self.telegram = TelegramNotifier(
            bot_token=self.env.telegram_bot_token,
            chat_id=self.env.telegram_chat_id,
            mock_mode=mock_telegram,
        )

        self.app = create_app(self.store)
        self._running = False
        self._was_missing = False

    async def _monitor_loop(self) -> None:
        """Monitor heartbeat status and send alerts."""
        while self._running:
            try:
                if self.store.should_alert_missing():
                    # Run external probe
                    probe_result = await self.probe.check()

                    # Use last_heartbeat or fallback to now if never received
                    last_hb = self.store.last_heartbeat or datetime.now(UTC)

                    # Generate and send alert
                    alert = self.alert_engine.create_monitor_lost_alert(
                        last_heartbeat=last_hb,
                        wan_states=self.store.get_last_wan_states(),
                        probe_result=probe_result,
                    )
                    await self.telegram.send_alert(alert)
                    self._was_missing = True

                elif self._was_missing and not self.store.is_missing():
                    # Recovered
                    alert = self.alert_engine.create_monitor_recovered_alert()
                    await self.telegram.send_alert(alert)
                    self._was_missing = False

                await asyncio.sleep(10)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                await asyncio.sleep(10)

    async def _probe_loop(self) -> None:
        """Periodic external probe."""
        if not self.probe.enabled:
            return

        while self._running:
            try:
                await asyncio.sleep(self.config.external_probe.interval)
                result = await self.probe.check()
                logger.debug(f"Periodic probe result: {result.value}")
            except Exception as e:
                logger.error(f"Probe loop error: {e}")

    async def _dns_monitor_loop(self) -> None:
        """Periodic DNS record monitoring."""
        if not self.dns_monitor:
            return

        while self._running:
            try:
                alerts = self.dns_monitor.check()
                for alert in alerts:
                    await self.telegram.send_alert(alert)
                await asyncio.sleep(self.config.dns_monitor.interval)
            except Exception as e:
                logger.error(f"DNS monitor loop error: {e}")
                await asyncio.sleep(60)

    async def start(self) -> None:
        """Start the remote sentinel."""
        self._running = True
        logger.info("Starting remote sentinel...")

        # Start background tasks
        monitor_task = asyncio.create_task(self._monitor_loop())
        probe_task = asyncio.create_task(self._probe_loop())
        dns_task = asyncio.create_task(self._dns_monitor_loop())

        # Run uvicorn server
        config = uvicorn.Config(
            self.app,
            host=self.config.heartbeat.listen_host,
            port=self.config.heartbeat.listen_port,
            log_level="info",
        )
        server = uvicorn.Server(config)

        try:
            await server.serve()
        finally:
            self._running = False
            monitor_task.cancel()
            probe_task.cancel()
            dns_task.cancel()

    async def stop(self) -> None:
        """Stop the remote sentinel."""
        self._running = False
        logger.info("Remote sentinel stopped")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="WAN Router Remote Sentinel")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("remote/config.yaml"),
        help="Path to config file",
    )
    parser.add_argument(
        "--mock-telegram",
        action="store_true",
        help="Use mock Telegram (print to console)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create sentinel
    sentinel = RemoteSentinel(
        config_path=args.config,
        mock_telegram=args.mock_telegram,
    )

    # Run
    try:
        asyncio.run(sentinel.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
