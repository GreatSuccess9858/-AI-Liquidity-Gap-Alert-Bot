"""Base classes for exchange order book monitoring."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Awaitable
import asyncio
from datetime import datetime


@dataclass
class OrderBookSnapshot:
    """Snapshot of an order book at a point in time."""

    exchange: str
    symbol: str
    bids: list[tuple[float, float]]  # [(price, size), ...] sorted best bid first
    asks: list[tuple[float, float]]  # [(price, size), ...] sorted best ask first
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def best_bid(self) -> tuple[float, float] | None:
        return self.bids[0] if self.bids else None

    def best_ask(self) -> tuple[float, float] | None:
        return self.asks[0] if self.asks else None

    def mid_price(self) -> float | None:
        if self.best_bid() and self.best_ask():
            return (self.best_bid()[0] + self.best_ask()[0]) / 2
        return None

    def total_bid_liquidity_usd(self) -> float:
        return sum(price * size for price, size in self.bids)

    def total_ask_liquidity_usd(self) -> float:
        return sum(price * size for price, size in self.asks)

    def total_bid_liquidity_usd(self) -> float:
        return sum(price * size for price, size in self.bids)


OrderBookCallback = Callable[[OrderBookSnapshot], Awaitable[None]]


class OrderBookMonitor(ABC):
    """Abstract base for exchange order book monitors."""

    def __init__(
        self,
        symbol: str,
        callback: OrderBookCallback,
        depth: int = 100,
    ):
        self.symbol = symbol
        self.callback = callback
        self.depth = depth
        self._running = False
        self._task: asyncio.Task | None = None

    @abstractmethod
    def _get_ws_url(self) -> str:
        pass

    @abstractmethod
    def _symbol_for_exchange(self) -> str:
        """Convert display symbol (e.g. BTC/USDT) to exchange format."""
        pass

    @abstractmethod
    async def _connect_and_subscribe(self) -> None:
        pass

    @abstractmethod
    async def _connect_and_subscribe(self) -> None:
        pass
        
    @abstractmethod
    def _parse_message(self, raw: dict) -> OrderBookSnapshot | None:
        pass

    async def start(self) -> None:
        """Start the monitor."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        print(f"[{self.__class__.__name__}] Started monitoring {self.symbol}")

    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print(f"[{self.__class__.__name__}] Stopped monitoring {self.symbol}")
