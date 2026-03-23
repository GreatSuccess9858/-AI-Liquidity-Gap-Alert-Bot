"""
Configuration for the AI Liquidity Gap Alert Bot.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    """Bot configuration."""

    # Symbols to monitor. Use BTC/USDT for Binance, BTC/USD for Coinbase.
    symbols_binance: List[str] = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    symbols_coinbase: List[str] = field(default_factory=lambda: ["BTC/USD", "ETH/USD"])
    symbols_coinbase: List[str] = field(default_factory=lambda: ["BTC/USD", "THE/USD"])

    # Exchanges to monitor
    exchanges: List[str] = field(default_factory=lambda: ["binance", "coinbase"])

    # Liquidity gap detection thresholds
    min_wall_size_usd: float = 500_000  # Minimum wall size to track (USD)
    wall_removal_threshold: float = 0.8  # % of wall that must disappear to trigger (0.8 = 80%)
    time_window_seconds: float = 60.0  # Max time window to consider as "sudden" removal
    min_confidence: float = 0.6  # Minimum confidence (0-1) to send alert

    # Order book depth to monitor (number of levels)
    order_book_depth: int = 100

    # WebSocket URLs
    binance_ws_url: str = "wss://stream.binance.com:9443/ws"
    coinbase_ws_url: str = "wss://ws-feed.exchange.coinbase.com"

    # Alert output
    alert_to_console: bool = True
    alert_to_file: bool = True
    alert_to_control: bool = True
    alert_file_path: str = "alerts.log"


config = Config()
