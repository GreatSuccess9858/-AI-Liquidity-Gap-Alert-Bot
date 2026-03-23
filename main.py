"""
AI Liquidity Gap Alert Bot

Monitors order books from Binance and Coinbase, detects when large buy/sell
walls suddenly disappear, and alerts traders before potential price moves.
"""
import asyncio

from config import config
from src.exchanges import BinanceOrderBookMonitor, CoinbaseOrderBookMonitor
from src.analyzer import LiquidityGapAnalyzer
from src.alerts import AlertManager


async def main() -> None:
    alert_manager = AlertManager(
        to_console=config.alert_to_console,
        to_file=config.alert_to_file,
        file_path=config.alert_file_path,
    )

    analyzer = LiquidityGapAnalyzer(
        min_wall_size_usd=config.min_wall_size_usd,
        wall_removal_threshold=config.wall_removal_threshold,
        time_window_seconds=config.time_window_seconds,
        min_confidence=config.min_confidence,
        on_alert=alert_manager.send,
    )

    monitors: list = []

    async def on_snapshot(snapshot):
        await analyzer.process_snapshot(snapshot)

    exchanges_lower = [e.lower() for e in config.exchanges]
    if "binance" in exchanges_lower:
        for symbol in config.symbols_binance:
            monitors.append(
                BinanceOrderBookMonitor(symbol, on_snapshot, config.order_book_depth)
            )
    if "coinbase" in exchanges_lower:
        for symbol in config.symbols_coinbase:
            monitors.append(
                CoinbaseOrderBookMonitor(symbol, on_snapshot, config.order_book_depth)
            )

    for m in monitors:
        await m.start()

    print("\n🚀 AI Liquidity Gap Alert Bot running.")
    all_symbols = set(config.symbols_binance) | set(config.symbols_coinbase)
    print(f"   Monitoring: {', '.join(sorted(all_symbols))} on {', '.join(config.exchanges)}")
    print(f"   Min wall size: ${config.min_wall_size_usd:,.0f}")
    print("   Press Ctrl+C to stop.\n")

    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        for m in monitors:
            try:
                await m.stop()
            except Exception:
                pass
        print("\nStopped.")
          exchanges_lower = [e.lower() for e in config.exchanges]
    if "binance" in exchanges_lower:
        for symbol in config.symbols_binance:
            monitors.append(
                BinanceOrderBookMonitor(symbol, on_snapshot, config.order_book_depth)
            )
    if "coinbase" in exchanges_lower:
        for symbol in config.symbols_coinbase:
            monitors.append(
                CoinbaseOrderBookMonitor(symbol, on_snapshot, config.order_book_depth)
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
