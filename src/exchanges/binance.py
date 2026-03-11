"""Binance order book monitor via WebSocket depth stream."""
import json
import asyncio
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed

from .base import OrderBookMonitor, OrderBookSnapshot


class BinanceOrderBookMonitor(OrderBookMonitor):
    """Monitors Binance spot order book via WebSocket depth stream."""

    def __init__(self, symbol: str, callback, depth: int = 100):
        super().__init__(symbol, callback, depth)
        self._bids: list[tuple[float, float]] = []
        self._asks: list[tuple[float, float]] = []
        self._last_update_id = 0
        self._ws_url = "wss://stream.binance.com:9443/ws"

    def _symbol_for_exchange(self) -> str:
        return self.symbol.replace("/", "").upper()

    def _get_ws_url(self) -> str:
        stream = f"{self._symbol_for_exchange().lower()}@depth{self.depth}@100ms"
        return f"wss://stream.binance.com:9443/ws/{stream}"

    def _parse_message(self, raw: dict) -> OrderBookSnapshot | None:
        """Parse Binance depth stream message."""
        if "lastUpdateId" not in raw or "bids" not in raw or "asks" not in raw:
            return None

        def to_tuples(levels: list) -> list[tuple[float, float]]:
            return [(float(p), float(q)) for p, q in levels if float(q) > 0]

        self._bids = sorted(to_tuples(raw["bids"]), key=lambda x: -x[0])[: self.depth]
        self._asks = sorted(to_tuples(raw["asks"]), key=lambda x: x[0])[: self.depth]
        self._last_update_id = raw["lastUpdateId"]

        return OrderBookSnapshot(
            exchange="Binance",
            symbol=self.symbol,
            bids=self._bids,
            asks=self._asks,
            timestamp=datetime.utcnow(),
        )

    async def _connect_and_subscribe(self) -> None:
        url = self._get_ws_url()
        async with websockets.connect(
            url,
            ping_interval=20,
            ping_timeout=60,
            close_timeout=5,
        ) as ws:
            async for msg in ws:
                if not self._running:
                    break
                try:
                    data = json.loads(msg)
                    snapshot = self._parse_message(data)
                    if snapshot:
                        await self.callback(snapshot)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[Binance] Parse error: {e}")

    async def _run_loop(self) -> None:
        """Run connection loop with reconnection."""
        backoff = 1
        while self._running:
            try:
                await self._connect_and_subscribe()
            except (ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                if self._running:
                    print(f"[Binance] Disconnected: {e}. Reconnecting in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
            except asyncio.CancelledError:
                break
            else:
                backoff = 1
