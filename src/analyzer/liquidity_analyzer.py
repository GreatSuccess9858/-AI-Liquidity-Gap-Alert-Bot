"""
AI Liquidity Gap Analyzer.

Detects when large buy/sell walls suddenly disappear from order books,
which may precede rapid price moves.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Awaitable

from ..exchanges.base import OrderBookSnapshot


@dataclass
class LiquidityGapAlert:
    """An alert about a detected liquidity gap."""

    symbol: str
    exchange: str
    side: str  # "buy" or "sell"
    event: str  # "Buy wall removed" or "Sell wall removed"
    direction_hint: str  # "Possible upward breakout" or "Possible downward move"
    confidence: float  # 0-1
    wall_size_usd: float
    price_level: float
    mid_price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_display_string(self) -> str:
        conf_pct = int(self.confidence * 100)
        return (
            f"\n{'='*50}\n"
            f"Liquidity Gap Detected\n"
            f"{self.symbol}\n"
            f"Exchange: {self.exchange}\n"
            f"{self.event}\n"
            f"{self.direction_hint}\n"
            f"Confidence: {conf_pct}%\n"
            f"{'='*50}\n"
        )


class LiquidityGapAnalyzer:
    """
    Tracks order book snapshots and detects when large walls (concentrated
    liquidity at a price level) suddenly disappear.
    """

    def __init__(
        self,
        min_wall_size_usd: float = 500_000,
        wall_removal_threshold: float = 0.8,
        time_window_seconds: float = 60.0,
        min_confidence: float = 0.6,
        on_alert: Callable[[LiquidityGapAlert], Awaitable[None]] | None = None,
    ):
        self.min_wall_size_usd = min_wall_size_usd
        self.wall_removal_threshold = wall_removal_threshold
        self.time_window_seconds = time_window_seconds
        self.min_confidence = min_confidence
        self.on_alert = on_alert

        self._last_snapshots: dict[tuple[str, str], OrderBookSnapshot] = {}
        self._prev_analyzed: dict[tuple[str, str], OrderBookSnapshot] = {}
        self._last_processed: dict[tuple[str, str], datetime] = {}
        self._analysis_interval_seconds: float = 2.0

    def _extract_walls(
        self, snapshot: OrderBookSnapshot
    ) -> tuple[dict[float, float], dict[float, float]]:
        """Extract significant walls (price levels with large size) from snapshot."""
        bid_walls = {}
        ask_walls = {}
        mid = snapshot.mid_price() or 0.0
        if mid <= 0:
            return bid_walls, ask_walls

        for price, size in snapshot.bids:
            size_usd = price * size
            if size_usd >= self.min_wall_size_usd:
                bid_walls[price] = size_usd

        for price, size in snapshot.asks:
            size_usd = price * size
            if size_usd >= self.min_wall_size_usd:
                ask_walls[price] = size_usd

        return bid_walls, ask_walls

    def _compute_confidence(
        self,
        wall_size_usd: float,
        time_elapsed_seconds: float,
        side: str,
        mid_price: float,
        price_level: float,
    ) -> float:
        """
        AI-inspired confidence score based on:
        - How large the wall was (bigger = more significant)
        - How quickly it disappeared (faster = more suspicious)
        - Proximity to mid price (closer = more impactful)
        """
        size_score = min(1.0, wall_size_usd / (self.min_wall_size_usd * 5))
        speed_score = 1.0 if time_elapsed_seconds < 10 else max(0, 1 - time_elapsed_seconds / 120)
        distance_pct = abs(price_level - mid_price) / mid_price if mid_price else 0.01
        proximity_score = max(0.3, 1.0 - distance_pct * 20)

        confidence = (size_score * 0.4 + speed_score * 0.35 + proximity_score * 0.25)
        return round(min(1.0, confidence), 2)

    def _get_direction_hint(self, side: str) -> str:
        """Interpret what the wall removal likely means for price."""
        if side == "buy":
            return "Possible upward breakout"  # Big buyer may be repositioning to buy
        return "Possible downward move"  # Big seller may be repositioning to sell

    def _get_event_description(self, side: str) -> str:
        if side == "buy":
            return "Buy wall removed"
        return "Sell wall removed"

    async def process_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        """
        Process a new order book snapshot. Compare with previous state
        to detect walls that have disappeared.
        """
        key_ob = (snapshot.exchange, snapshot.symbol)
        self._last_snapshots[key_ob] = snapshot

        last = self._last_processed.get(key_ob)
        if last and (snapshot.timestamp - last).total_seconds() < self._analysis_interval_seconds:
            return
        self._last_processed[key_ob] = snapshot.timestamp

        current_bid_walls, current_ask_walls = self._extract_walls(snapshot)
        mid = snapshot.mid_price() or 0.0

        prev = self._prev_analyzed.get(key_ob)
        if not prev:
            self._prev_analyzed[key_ob] = snapshot
            return

        prev_bid_walls, prev_ask_walls = self._extract_walls(prev)
        time_elapsed = (snapshot.timestamp - prev.timestamp).total_seconds()
        if time_elapsed > self.time_window_seconds:
            self._prev_analyzed[key_ob] = snapshot
            return

        for side, prev_walls, current_walls in [
            ("buy", prev_bid_walls, current_bid_walls),
            ("sell", prev_ask_walls, current_ask_walls),
        ]:
            for price, prev_size in prev_walls.items():
                if prev_size < self.min_wall_size_usd:
                    continue
                current_size = current_walls.get(price, 0)
                removal_ratio = 1 - (current_size / prev_size) if prev_size > 0 else 1.0

                if removal_ratio >= self.wall_removal_threshold:
                    confidence = self._compute_confidence(
                        prev_size, time_elapsed, side, mid, price
                    )
                    if confidence >= self.min_confidence:
                        alert = LiquidityGapAlert(
                            symbol=snapshot.symbol,
                            exchange=snapshot.exchange,
                            side=side,
                            event=self._get_event_description(side),
                            direction_hint=self._get_direction_hint(side),
                            confidence=confidence,
                            wall_size_usd=prev_size,
                            price_level=price,
                            mid_price=mid,
                            timestamp=snapshot.timestamp,
                        )
                        if self.on_alert:
                            await self.on_alert(alert)

        self._prev_analyzed[key_ob] = snapshot
