"""Local monitor main entry point."""

import argparse
import asyncio
import logging
import signal
from pathlib import Path
from typing import Protocol

from local.alert_engine import AlertEngine
from local.heartbeat import HeartbeatSender
from local.snmp_poller import MockSNMPPoller, SNMPPoller
from local.syslog_receiver import SyslogReceiver
from shared.config import EnvConfig, load_local_config
from shared.models import AlertEvent, SyslogEvent, WANState
from shared.telegram import TelegramNotifier


class SNMPPollerProtocol(Protocol):
    """Protocol for SNMP pollers."""

    async def poll(self) -> dict[str, WANState]:
        """Poll all WAN interfaces and return their states."""
        ...

logger = logging.getLogger(__name__)


class LocalMonitor:
    """Main local monitor orchestrator."""

    def __init__(
        self,
        config_path: Path,
        mock_snmp: bool = False,
        mock_telegram: bool = False,
    ):
        self.config = load_local_config(config_path)
        self.env = EnvConfig()
        self.mock_snmp = mock_snmp
        self.mock_telegram = mock_telegram

        # Initialize components
        self.poller: SNMPPollerProtocol
        if mock_snmp:
            self.poller = MockSNMPPoller(
                wan_gateways=self.config.router.wan_gateways or None,
                wan_interfaces=self.config.router.wan_interfaces or None,
            )
        else:
            auth_key = self.env.snmp_auth_key or self.config.router.snmp_auth_key
            self.poller = SNMPPoller(
                host=self.config.router.host,
                username=self.config.router.snmp_username,
                auth_key=auth_key,
                wan_gateways=self.config.router.wan_gateways,
                wan_interfaces=self.config.router.wan_interfaces,
                auth_protocol=self.config.router.snmp_auth_protocol,
                port=self.config.router.snmp_port,
            )

        self.alert_engine = AlertEngine(
            router_ip=self.config.router.host,
            router_name=self.config.router.name,
        )

        self.telegram = TelegramNotifier(
            bot_token=self.env.telegram_bot_token,
            chat_id=self.env.telegram_chat_id,
            mock_mode=mock_telegram,
        )

        self.heartbeat = HeartbeatSender(
            remote_url=self.config.heartbeat.remote_url,
        )

        self.syslog: SyslogReceiver | None = None
        if self.config.syslog.enabled:
            self.syslog = SyslogReceiver(
                port=self.config.syslog.port,
                bind_address=self.config.syslog.bind_address,
            )
            self.syslog.add_callback(self._on_syslog_event)

        self._running = False
        self._recent_events: list[AlertEvent] = []

    def _on_syslog_event(self, event: SyslogEvent) -> None:
        """Handle incoming syslog event."""
        alerts = self.alert_engine.process_syslog_event(event)
        for alert in alerts:
            self._recent_events.append(alert)
            asyncio.create_task(self.telegram.send_alert(alert))

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                # Determine poll interval
                if self.alert_engine.should_use_alert_interval():
                    interval = self.config.polling.alert_interval
                else:
                    interval = self.config.polling.normal_interval

                # Poll SNMP
                wan_states = await self.poller.poll()

                # Process states and send alerts
                for state in wan_states.values():
                    alerts = self.alert_engine.process_wan_state(state, all_states=wan_states)
                    for alert in alerts:
                        self._recent_events.append(alert)
                        await self.telegram.send_alert(alert)

                # Trim recent events list
                self._recent_events = self._recent_events[-100:]

                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Poll loop error: {e}")
                await asyncio.sleep(10)

    async def _heartbeat_loop(self) -> None:
        """Heartbeat sending loop."""
        while self._running:
            try:
                wan_states = self.alert_engine.get_current_wan_states()
                await self.heartbeat.send(wan_states, self._recent_events)
                await asyncio.sleep(self.config.heartbeat.interval)
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(10)

    async def start(self) -> None:
        """Start the local monitor."""
        self._running = True
        logger.info("Starting local monitor...")

        # Start syslog receiver
        if self.syslog:
            await self.syslog.start()

        # Start loops
        await asyncio.gather(
            self._poll_loop(),
            self._heartbeat_loop(),
        )

    async def stop(self) -> None:
        """Stop the local monitor."""
        self._running = False
        if self.syslog:
            await self.syslog.stop()
        logger.info("Local monitor stopped")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="WAN Router Local Monitor")
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=Path("local/config.yaml"),
        help="Path to config file",
    )
    parser.add_argument(
        "--mock-snmp",
        action="store_true",
        help="Use mock SNMP poller",
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
        format="%(name)s - %(levelname)s - %(message)s",
    )
    # Suppress noisy third-party loggers
    logging.getLogger("pysnmp").setLevel(logging.WARNING)
    logging.getLogger("pyasn1").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Create monitor
    monitor = LocalMonitor(
        config_path=args.config,
        mock_snmp=args.mock_snmp,
        mock_telegram=args.mock_telegram,
    )

    # Handle signals
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler() -> None:
        logger.info("Received shutdown signal")
        loop.create_task(monitor.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    try:
        loop.run_until_complete(monitor.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(monitor.stop())
        loop.close()


if __name__ == "__main__":
    main()
