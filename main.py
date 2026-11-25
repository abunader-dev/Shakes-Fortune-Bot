import argparse
import asyncio
import logging
import time
import yaml
from telegram.ext import Application, CommandHandler

from bot_state import BotState
import telegram_handlers as handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def post_init_autostart(application: Application) -> None:
    """Start the Playwright ad-farming loop automatically on launch."""
    from sf_bot import run_sf_bot

    state = handlers.state
    config = handlers.config
    if state.running:
        return

    state.running = True
    state.start_time = time.time()
    state.current_status = "Iniciando..."

    owner_id = config.get("owner_chat_id", 0)
    if owner_id:
        application.job_queue.run_repeating(
            handlers.periodic_report,
            interval=config["timing"]["report_interval"],
            first=config["timing"]["report_interval"],
            chat_id=owner_id,
            name=f"report_{owner_id}",
        )
        try:
            char_name = config.get("character_name", "Sin configurar")
            server_id = config.get("server_id", "")
            char_label = f"{char_name} ({server_id})" if server_id else char_name
            await application.bot.send_message(
                chat_id=owner_id,
                text=(
                    f"🚀 <b>Shakes &amp; Fortune iniciado desde la app</b>\n"
                    f"🧙 Personaje: <b>{char_label}</b>\n"
                    f"🔔 Reportes: Cada 5 minutos · Envía /stop para detener."
                ),
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Could not send startup Telegram notification: %s", exc)

    state.task = asyncio.create_task(run_sf_bot(state, config, application))
    logger.info("Autostart enabled: Playwright loop launched.")


async def post_shutdown(application: Application) -> None:
    """Clean up Playwright and save state after shutdown."""
    state = handlers.state
    if state:
        state.running = False
        if state.task and not state.task.done():
            state.task.cancel()
            try:
                await asyncio.wait_for(state.task, timeout=5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
    logger.info("post_shutdown: cleanup complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Shakes & Fortune Telegram + Playwright bot.")
    parser.add_argument(
        "--autostart",
        action="store_true",
        help="Start farming immediately on launch instead of waiting for /start.",
    )
    args = parser.parse_args()

    config = load_config()
    state = BotState()

    # Inject shared objects into handlers module
    handlers.state = state
    handlers.config = config

    builder = (
        Application.builder()
        .token(config["telegram_token"])
        .post_shutdown(post_shutdown)
    )
    if args.autostart:
        builder = builder.post_init(post_init_autostart)

    app = builder.build()

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("stop", handlers.cmd_stop))
    app.add_handler(CommandHandler("status", handlers.cmd_status))

    logger.info("Bot started. Waiting for commands...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
