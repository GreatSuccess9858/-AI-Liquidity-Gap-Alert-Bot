"""Coinbase order book monitor via WebSocket level2 channel."""
import json
import asyncio
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed

from .base import OrderBookMonitor, OrderBookSnapshot


class CoinbaseOrderBookMonitor(OrderBookMonitor):
    """Monitors Coinbase Exchange order book via level2 WebSocket channel."""

    def __init__(self, symbol: str, callback, depth: int = 100):
        super().__init__(symbol, callback, depth)
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}
        self._ws_url = "wss://ws-feed.exchange.coinbase.com"

    def _symbol_for_exchange(self) -> str:
        return self.symbol.replace("/", "-")

    def _get_ws_url(self) -> str:
        return self._ws_url

    def _to_sorted_tuples(self, d: dict) -> list[tuple[float, float]]:
        return sorted(
            [(p, q) for p, q in d.items() if q > 0],
            key=lambda x: x[0],
        )

    def _apply_snapshot(self, raw: dict) -> OrderBookSnapshot | None:
        if raw.get("type") != "snapshot":
            return None
        bids = raw.get("bids", [])
        asks = raw.get("asks", [])
        self._bids = {float(p): float(q) for p, q, _ in bids}
        self._asks = {float(p): float(q) for p, q, _ in asks}
        return self._build_snapshot()

    def _apply_l2update(self, raw: dict) -> OrderBookSnapshot | None:
        if raw.get("type") != "l2update":
            return None
        for change in raw.get("changes", []):
            side, price, size = change[0], float(change[1]), float(change[2])
            if side == "buy":
                if size == 0:
                    self._bids.pop(price, None)
                else:
                    self._bids[price] = size
            else:
                if size == 0:
                    self._asks.pop(price, None)
                else:
                    self._asks[price] = size
        return self._build_snapshot()

     def _apply_l2update(self, raw: dict) -> OrderBookSnapshot | None:
        if raw.get("type") != "l2update":
            return None
        for change in raw.get("changes", []):
            side, price, size = change[0], float(change[1]), float(change[2])
            if side == "buy":
                if size == 0:
                    self._bids.pop(price, None)
                else:
                    self._bids[price] = size
            else:
                if size == 0:
                    self._asks.pop(price, None)
                else:
                    self._asks[price] = size
        return self._build_snapshot()

    def _build_snapshot(self) -> OrderBookSnapshot:
        bid_list = sorted(self._bids.items(), key=lambda x: -x[0])[: self.depth]
        ask_list = sorted(self._asks.items(), key=lambda x: x[0])[: self.depth]
        return OrderBookSnapshot(
            exchange="Coinbase",
            symbol=self.symbol,
            bids=bid_list,
            asks=ask_list,
            timestamp=datetime.utcnow(),
        )

    def _parse_message(self, raw: dict) -> OrderBookSnapshot | None:
        msg_type = raw.get("type")
        if msg_type == "snapshot":
            return self._apply_snapshot(raw)
        if msg_type == "l2update":
            return self._apply_l2update(raw)
        return None

    async def _connect_and_subscribe(self) -> None:
        async with websockets.connect(
            self._ws_url,
            ping_interval=30,
            ping_timeout=10,
        ) as ws:
            subscribe = {
                "type": "subscribe",
                "product_ids": [self._symbol_for_exchange()],
                "channels": ["level2"],
            }
            await ws.send(json.dumps(subscribe))

            async for msg in ws:
                if not self._running:
                    break
                try:
                    data = json.loads(msg)
                    if data.get("type") in ("subscriptions", "channel"):
                        continue
                    snapshot = self._parse_message(data)
                    if snapshot:
                        await self.callback(snapshot)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"[Coinbase] Parse error: {e}")

    async def _run_loop(self) -> None:
        backoff = 1
        while self._running:
            try:
                await self._connect_and_subscribe()
            except (ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                if self._running:
                    print(f"[Coinbase] Disconnected: {e}. Reconnecting in {backoff}s...")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)
            except asyncio.CancelledError:
                break
            else:
                backoff = 1
