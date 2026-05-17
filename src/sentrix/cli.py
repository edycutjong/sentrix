"""CLI entry point for Sentrix."""

from __future__ import annotations

import asyncio
import logging
import sys

import click
from rich.console import Console
from rich.table import Table

from sentrix import __version__
from sentrix.config import SentinelConfig, WatchedAddress
from sentrix.core.poller import Poller

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("grpc").setLevel(logging.WARNING)


@click.group()
@click.version_option(version=__version__, prog_name="sentrix")
def cli() -> None:
    """🛡️ Sentrix — AI-powered DeFi position monitor for Injective.

    Monitor your Injective positions 24/7 and receive natural-language
    risk alerts via Telegram or Discord.
    """
    pass


@cli.command()
@click.option("--config", "-c", type=click.Path(), default=None, help="Path to config.yaml")
@click.option("--address", "-a", type=str, default=None, help="Injective address to watch")
@click.option("--demo", is_flag=True, default=False, help="Use mock data for demo")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Verbose logging")
@click.option("--once", is_flag=True, default=False, help="Poll once and exit")
def watch(
    config: str | None,
    address: str | None,
    demo: bool,
    verbose: bool,
    once: bool,
) -> None:
    """Start monitoring Injective positions.

    Examples:

        sentrix watch --demo

        sentrix watch --address inj1abc... --demo

        sentrix watch --config config.yaml
    """
    setup_logging(verbose)

    # Print banner
    console.print()
    console.print("╭──────────────────────────────────────────────────╮", style="cyan")
    console.print(
        f"│  🛡️  Sentrix v{__version__}                        │", style="cyan"
    )
    console.print("╰──────────────────────────────────────────────────╯", style="cyan")
    console.print()

    # Load config
    cfg = SentinelConfig.load(config)

    # Override with CLI args
    if demo:
        cfg.demo = True
    if address:
        cfg.addresses = [WatchedAddress(address=address, label="CLI")]

    # Default demo address if none configured
    if not cfg.addresses:
        if cfg.demo:
            cfg.addresses = [
                WatchedAddress(address="demo", label="Demo Trader")
            ]
        else:
            console.print(
                "❌ No addresses configured. Use --address or add to config.yaml",
                style="red",
            )
            sys.exit(1)

    mode = "DEMO MODE" if cfg.demo else cfg.network.upper()
    console.print(f"📡 Network: {mode}")
    console.print(f"👀 Watching: {len(cfg.addresses)} address(es)")
    console.print(f"⏱  Polling every {cfg.poll_interval_seconds}s")
    console.print(f"🔔 Alert rules: {len(cfg.alert_rules)} active")
    console.print()

    poller = Poller(cfg)

    if once:
        alerts = asyncio.run(poller.poll_once())
        if not alerts:
            console.print("✅ No risk events detected", style="green")
    else:
        try:
            asyncio.run(poller.start())
        except KeyboardInterrupt:
            console.print("\n👋 Sentrix stopped", style="dim")


@cli.command()
@click.option("--config", "-c", type=click.Path(), default=None, help="Path to config.yaml")
@click.option("--address", "-a", type=str, default=None, help="Injective address")
@click.option("--demo", is_flag=True, default=False, help="Use mock data")
def status(config: str | None, address: str | None, demo: bool) -> None:
    """Show current position summary.

    Examples:

        sentrix status --demo

        sentrix status --address inj1abc...
    """
    setup_logging(False)

    cfg = SentinelConfig.load(config)
    if demo:
        cfg.demo = True
    if address:
        cfg.addresses = [WatchedAddress(address=address)]
    if not cfg.addresses and cfg.demo:
        cfg.addresses = [WatchedAddress(address="demo", label="Demo Trader")]

    from sentrix.clients.injective import InjectiveClient

    async def _show_status() -> None:
        client = InjectiveClient(network=cfg.network, demo=cfg.demo)
        await client.initialize()

        for watched in cfg.addresses:
            snapshot = await client.fetch_portfolio(watched.address, watched.label)

            console.print()
            console.print(
                f"📊 Portfolio: {snapshot.label or snapshot.address}",
                style="bold cyan",
            )

            # Positions table
            if snapshot.derivative_positions:
                table = Table(title="Derivative Positions")
                table.add_column("Market", style="white")
                table.add_column("Side", style="white")
                table.add_column("Margin %", justify="right")
                table.add_column("PnL", justify="right")

                for pos in snapshot.derivative_positions:
                    margin_style = (
                        "green" if pos.margin_ratio > 1.5
                        else "yellow" if pos.margin_ratio > 1.2
                        else "red"
                    )
                    pnl_style = "green" if pos.unrealized_pnl >= 0 else "red"
                    margin_emoji = "✅" if pos.margin_ratio > 1.5 else "⚠️"

                    table.add_row(
                        pos.ticker,
                        f"{pos.direction.value.upper()} {pos.leverage}",
                        f"[{margin_style}]{margin_emoji} {pos.margin_ratio:.0%}[/]",
                        f"[{pnl_style}]${pos.unrealized_pnl:,.2f}[/]",
                    )
                console.print(table)

            # Spot balances
            if snapshot.spot_balances:
                console.print()
                console.print("💰 Spot Balances:", style="bold")
                for bal in snapshot.spot_balances:
                    usd = f" (${bal.usd_value:,.2f})" if bal.usd_value else ""
                    console.print(f"  • {bal.amount} {bal.display_denom}{usd}")

        await client.close()

    asyncio.run(_show_status())


@cli.command()
def history() -> None:
    """Show past alert history.

    Reads from the local SQLite database (sentinel.db).
    """
    from sentrix.storage.db import AlertStore

    async def _show_history() -> None:
        store = AlertStore()
        await store.initialize()
        alerts = await store.get_recent_alerts(limit=20)

        if not alerts:
            console.print("📭 No alerts in history", style="dim")
            return

        table = Table(title=f"Alert History ({len(alerts)} most recent)")
        table.add_column("Time", style="dim")
        table.add_column("Severity")
        table.add_column("Type")
        table.add_column("Title")

        severity_styles = {
            "low": "blue",
            "medium": "yellow",
            "high": "dark_orange",
            "critical": "bold red",
        }

        for a in alerts:
            style = severity_styles.get(a["severity"], "white")
            table.add_row(
                str(a["created_at"])[:19],
                f"[{style}]{a['severity'].upper()}[/]",
                a["alert_type"],
                a["title"],
            )

        console.print(table)

    asyncio.run(_show_history())


if __name__ == "__main__":
    cli()
