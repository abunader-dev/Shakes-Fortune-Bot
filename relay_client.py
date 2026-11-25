"""
Relay-mode Telegram client for Shakes & Fortune.

Connects the local bot to the shared Cloudflare Workers relay so every user can
control their own PC through @shakes_fortune_bot without needing a BotFather token.
"""
import asyncio
import logging
import time
from typing import Optional

import httpx

from bot_state import BotState
from sf_bot import run_sf_bot

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5.0


class RelayClient:
    def __init__(self, base_url: str, secret: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self.headers = {"Authorization": f"Bearer {self.secret}"}

    async def poll(self, client: httpx.AsyncClient) -> dict:
        resp = await client.get(f"{self.base_url}/api/poll", headers=self.headers, timeout=10.0)
        resp.raise_for_status()
        return resp.json()

    async def notify(self, client: httpx.AsyncClient, text: str) -> bool:
        try:
            resp = await client.post(
                f"{self.base_url}/api/notify",
                headers=self.headers,
                json={"text": text, "parse_mode": "HTML"},
                timeout=10.0,
            )
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception as exc:
            logger.warning("Relay notify failed: %s", exc)
            return False


def _char_label(config: dict) -> str:
    name = config.get("character_name", "Sin configurar")
    server = config.get("server_id", "")
    return f"{name} ({server})" if server else name


async def run_relay_bot(state: BotState, config: dict, *, autostart: bool = False) -> None:
    """Main pure-asyncio loop for relay-connected Telegram control + Playwright farming."""
    relay_cfg = config.get("relay", {})
    base_url = str(relay_cfg.get("url", "")).strip()
    secret = str(relay_cfg.get("client_secret", "")).strip()
    if not base_url or not secret:
        raise RuntimeError("Relay URL o client_secret faltante en config.yaml.")

    relay = RelayClient(base_url, secret)
    report_interval = float(config.get("timing", {}).get("report_interval", 300))
    stop_timeout = float(config.get("timing", {}).get("stop_timeout", 15))
    report_task: Optional[asyncio.Task] = None

    async with httpx.AsyncClient() as http:
        async def periodic_reports() -> None:
            try:
                while state.running:
                    await asyncio.sleep(report_interval)
                    if not state.running:
                        break
                    await relay.notify(
                        http,
                        f"🏛️ <b>Shakes &amp; Fortune — Estado</b>\n\n"
                        f"🧙 Personaje: {_char_label(config)}\n"
                        f"⏱️ Tiempo Activo: {state.elapsed_minutes()} min\n"
                        f"📺 Anuncios Vistos: {state.ads_watched}\n"
                        f"🔄 Estado Actual: {state.current_status}",
                    )
            except asyncio.CancelledError:
                pass

        async def start_farming(*, from_app: bool = False) -> None:
            nonlocal report_task
            if state.running and state.task and not state.task.done():
                await relay.notify(
                    http,
                    "🔔 <b>El bot ya está corriendo.</b>\n"
                    f"🧙 Personaje: <b>{_char_label(config)}</b>\n"
                    "Envía /status para ver el progreso o /stop para detenerlo.",
                )
                return

            state.running = True
            state.start_time = time.time()
            state.current_status = "Iniciando..."
            state.task = asyncio.create_task(run_sf_bot(state, config, None))
            if report_task and not report_task.done():
                report_task.cancel()
            report_task = asyncio.create_task(periodic_reports())

            origin = "desde la app" if from_app else "desde Telegram"
            await relay.notify(
                http,
                f"🚀 <b>Shakes &amp; Fortune inicializado ({origin})</b>\n"
                f"🧙 Personaje: <b>{_char_label(config)}</b>\n"
                f"🎯 Objetivo: Infinito (AFK)\n"
                f"🔔 Reportes: Cada {int(report_interval // 60)} minutos",
            )

        async def stop_farming() -> None:
            nonlocal report_task
            state.running = False
            if report_task and not report_task.done():
                report_task.cancel()
                try:
                    await report_task
                except asyncio.CancelledError:
                    pass
                report_task = None

            if state.task and not state.task.done():
                try:
                    await asyncio.wait_for(state.task, timeout=stop_timeout)
                except asyncio.TimeoutError:
                    state.task.cancel()
                    logger.warning("Playwright task did not stop in time; cancelled.")
                except Exception:
                    pass

            await relay.notify(
                http,
                "🔕 <b>Bot detenido.</b>\n"
                "No recibirás más reportes hasta que envíes /start nuevamente.",
            )

        async def send_status() -> None:
            await relay.notify(
                http,
                f"📊 <b>Reporte instantáneo</b>\n\n"
                f"🧙 Personaje: {_char_label(config)}\n"
                f"⏱️ Tiempo Activo: {state.elapsed_minutes()} min\n"
                f"📺 Anuncios Vistos: {state.ads_watched}\n"
                f"🔄 Estado Actual: {state.current_status}",
            )

        logger.info("Connected to Shakes & Fortune Relay (%s). Waiting for commands...", base_url)
        if autostart:
            await start_farming(from_app=True)

        try:
            while True:
                try:
                    data = await relay.poll(http)
                    if not data.get("linked", True):
                        logger.warning("This PC was unlinked in Telegram. Re-link from the launcher.")
                    cmd = data.get("command")
                    if cmd == "start":
                        logger.info("Received /start from Telegram relay.")
                        await start_farming(from_app=False)
                    elif cmd == "stop":
                        logger.info("Received /stop from Telegram relay.")
                        await stop_farming()
                    elif cmd == "status":
                        logger.info("Received /status from Telegram relay.")
                        await send_status()
                except httpx.HTTPError as exc:
                    logger.warning("Relay poll network error: %s", exc)
                except Exception as exc:
                    logger.exception("Unexpected relay error: %s", exc)

                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Relay loop cancelled; shutting down...")
        finally:
            state.running = False
            if report_task and not report_task.done():
                report_task.cancel()
            if state.task and not state.task.done():
                state.task.cancel()
                try:
                    await asyncio.wait_for(state.task, timeout=5)
                except Exception:
                    pass
