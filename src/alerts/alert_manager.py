"""Alert manager - outputs liquidity gap alerts to console and/or file."""
import asyncio
from pathlib import Path

from ..analyzer import LiquidityGapAlert


class AlertManager:
    """Handles output of liquidity gap alerts."""

    def __init__(
        self,
        to_console: bool = True,
        to_file: bool = True,
        file_path: str = "alerts.log",
    ):
        self.to_console = to_console
        self.to_file = to_file
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()

    async def send(self, alert: LiquidityGapAlert) -> None:
        """Send an alert to configured outputs."""
        text = alert.to_display_string()
        async with self._lock:
            if self.to_console:
                print(text)
            if self.to_file:
                with open(self.file_path, "a", encoding="utf-8") as f:
                    f.write(text)
                    f.write("\n")
