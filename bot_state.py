from dataclasses import dataclass, field
from typing import Optional
import asyncio
import time


@dataclass
class BotState:
    running: bool = False
    ads_watched: int = 0
    lucky_coins: int = 0
    current_status: str = "Detenido"
    last_error: Optional[str] = None
    task: Optional[asyncio.Task] = None
    consecutive_errors: int = 0
    consecutive_session_recoveries: int = 0
    start_time: Optional[float] = None

    def elapsed_minutes(self) -> int:
        if self.start_time is None:
            return 0
        return int((time.time() - self.start_time) / 60)
