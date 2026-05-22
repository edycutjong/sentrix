"""Injective SDK client wrapper for Sentrix.

Abstracts the Injective gRPC APIs into a simple interface
for fetching portfolio data (positions, balances, prices).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from sentrix.models.position import (
    DerivativePosition,
    PortfolioSnapshot,
    PositionDirection,
    SpotBalance,
)

logger = logging.getLogger(__name__)


class InjectiveClient:
    """Client for querying Injective chain state.

    Wraps the injective-py SDK to provide a clean interface for:
    - Fetching subaccount balances
    - Fetching derivative positions
    - Fetching spot balances
    - Fetching oracle prices
    """

    def __init__(self, network: str = "mainnet", demo: bool = False) -> None:
        """Initialize the Injective client.

        Args:
            network: 'mainnet' or 'testnet'
            demo: If True, use mock data instead of live chain
        """
        self.network_name = network
        self.demo = demo
        self._client = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the async gRPC client connection."""
        if self.demo:
            logger.info("Running in demo mode — using mock data")
            self._initialized = True
            return

        try:
            from pyinjective.async_client import AsyncClient  # type: ignore
            from pyinjective.core.network import Network  # type: ignore

            net = Network.mainnet() if self.network_name == "mainnet" else Network.testnet()
            self._client = AsyncClient(net)
            self._initialized = True
            logger.info("Connected to Injective %s", self.network_name)
        except ImportError:
            logger.warning(
                "injective-py not installed. Install with: pip install injective-py"
            )
            logger.info("Falling back to demo mode")
            self.demo = True
            self._initialized = True
        except Exception as e:
            logger.error("Failed to connect to Injective: %s", e)
            raise

    async def fetch_portfolio(self, address: str, label: str | None = None) -> PortfolioSnapshot:
        """Fetch complete portfolio snapshot for an address.

        Args:
            address: Injective address (inj1...)
            label: Optional human-readable label

        Returns:
            PortfolioSnapshot with all positions and balances
        """
        if self.demo:
            return self._load_demo_portfolio(address, label)

        spot_balances = await self._fetch_spot_balances(address)
        derivative_positions = await self._fetch_derivative_positions(address)

        return PortfolioSnapshot(
            address=address,
            label=label,
            spot_balances=spot_balances,
            derivative_positions=derivative_positions,
        )

    async def _fetch_spot_balances(self, address: str) -> list[SpotBalance]:
        """Fetch spot/bank balances for an address.

        Uses ChainGrpcBankApi.fetch_balances() to get all native balances.
        """
        if not self._client:
            return []

        try:
            response = await self._client.fetch_bank_balances(address)
            balances = []
            for bal in response.get("balances", []):
                balances.append(
                    SpotBalance(
                        denom=bal["denom"],
                        amount=bal["amount"],
                    )
                )
            return balances
        except Exception as e:
            logger.error("Failed to fetch balances for %s: %s", address, e)
            return []

    async def _fetch_derivative_positions(self, address: str) -> list[DerivativePosition]:
        """Fetch all open derivative positions for an address.

        Uses IndexerGrpcDerivativeApi.fetch_derivative_positions()
        to get positions with pre-computed margin ratios and liquidation prices.
        """
        if not self._client:
            return []

        try:
            # The Injective indexer returns positions with all computed fields
            response = await self._client.fetch_derivative_positions(
                subaccount_id=address,
            )
            positions = []
            for pos in response.get("positions", []):
                direction = (
                    PositionDirection.LONG
                    if pos.get("direction") == "long"
                    else PositionDirection.SHORT
                )
                positions.append(
                    DerivativePosition(
                        market_id=pos.get("marketId", ""),
                        ticker=pos.get("ticker", "Unknown"),
                        direction=direction,
                        quantity=pos.get("quantity", "0"),
                        entry_price=pos.get("entryPrice", "0"),
                        mark_price=pos.get("markPrice", "0"),
                        liquidation_price=pos.get("liquidationPrice", "0"),
                        margin=pos.get("margin", "0"),
                        leverage=f"{pos.get('leverage', '1')}x",
                    )
                )
            return positions
        except Exception as e:
            logger.error("Failed to fetch positions for %s: %s", address, e)
            return []

    def _load_demo_portfolio(
        self, address: str, label: str | None = None
    ) -> PortfolioSnapshot:
        """Load demo portfolio from fixture data."""
        fixtures_path = Path(__file__).parent.parent.parent.parent / "data" / "fixtures"
        mock_file = fixtures_path / "mock_positions.json"

        if mock_file.exists():
            data = json.loads(mock_file.read_text())
            # Find matching address or return first entry
            for entry in data:
                if entry["address"] == address or address == "demo":
                    return self._parse_fixture_entry(entry)
            # Default: return first entry
            if data:
                entry = data[0]
                if label:
                    entry["label"] = label
                return self._parse_fixture_entry(entry)

        # Fallback: generate hardcoded demo data
        return self._generate_demo_data(address, label)

    def _parse_fixture_entry(self, entry: dict) -> PortfolioSnapshot:
        """Parse a fixture JSON entry into a PortfolioSnapshot."""
        positions = []
        for pos in entry.get("positions", []):
            positions.append(
                DerivativePosition(
                    market_id=f"0x_mock_{pos['market'].replace('/', '_').lower()}",
                    ticker=pos["market"],
                    direction=PositionDirection(pos["direction"]),
                    quantity=str(pos["quantity"]),
                    entry_price=str(pos["entry_price"]),
                    mark_price=str(pos["mark_price"]),
                    liquidation_price=str(pos["liquidation_price"]),
                    margin=str(pos["margin"]),
                    leverage=pos.get("leverage", "1x"),
                )
            )

        balances = []
        for bal in entry.get("spot_balances", []):
            balances.append(
                SpotBalance(
                    denom=bal["denom"],
                    amount=str(bal["amount"]),
                )
            )

        return PortfolioSnapshot(
            address=entry.get("address", "inj1demo"),
            label=entry.get("label"),
            derivative_positions=positions,
            spot_balances=balances,
        )

    def _generate_demo_data(
        self, address: str, label: str | None = None
    ) -> PortfolioSnapshot:
        """Generate hardcoded demo data when no fixtures available."""
        return PortfolioSnapshot(
            address=address,
            label=label or "Demo Trader",
            derivative_positions=[
                DerivativePosition(
                    market_id="0x_demo_inj_usdt_perp",
                    ticker="INJ/USDT PERP",
                    direction=PositionDirection.LONG,
                    quantity="3200",
                    entry_price="14.30",
                    mark_price="13.85",
                    liquidation_price="12.58",
                    margin="8200",
                    leverage="5x",
                ),
                DerivativePosition(
                    market_id="0x_demo_eth_usdt_perp",
                    ticker="ETH/USDT PERP",
                    direction=PositionDirection.SHORT,
                    quantity="2.5",
                    entry_price="3800",
                    mark_price="3750",
                    liquidation_price="4200",
                    margin="4750",
                    leverage="3x",
                ),
            ],
            spot_balances=[
                SpotBalance(denom="inj", amount="150.5", usd_value=2085.0),
                SpotBalance(
                    denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
                    amount="2340.50",
                    usd_value=2340.50,
                ),
            ],
        )

    async def close(self) -> None:
        """Close the client connection."""
        self._client = None
        self._initialized = False
