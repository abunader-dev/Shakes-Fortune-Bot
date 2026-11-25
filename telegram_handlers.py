import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot_state import BotState

logger = logging.getLogger(__name__)

# Will be injected by main.py
state: BotState = None
config: dict = None


def _is_authorized(chat_id: int) -> bool:
    """Allow first user when owner_chat_id is unset (0), otherwise restrict to owner."""
    owner_id = config.get("owner_chat_id", 0)
    return owner_id == 0 or chat_id == owner_id


def _character_label() -> str:
    name = config.get("character_name", "Sin configurar")
    server = config.get("server_id", "")
    return f"{name} ({server})" if server else name


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the bot or reactivate periodic notifications."""
    chat_id = update.effective_chat.id

    if not _is_authorized(chat_id):
        await update.message.reply_text("⛔ No estás autorizado para controlar este bot.")
        return

    # Save owner chat_id on first use so each friend's bot locks to their Telegram account
    if config.get("owner_chat_id", 0) == 0:
        import yaml
        config["owner_chat_id"] = chat_id
        with open("config.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)

    if state.running:
        await update.message.reply_text(
            "🔔 <b>Notificaciones reactivadas.</b>\n"
            "Volverás a recibir reportes cada 5 minutos.\n"
            "Envía /stop para detenerlas.",
            parse_mode="HTML",
        )
        return

    # First launch: start the bot
    state.running = True
    import time
    state.start_time = time.time()
    state.current_status = "Iniciando..."

    # Schedule periodic reports
    context.job_queue.run_repeating(
        periodic_report,
        interval=config["timing"]["report_interval"],
        first=config["timing"]["report_interval"],
        chat_id=chat_id,
        name=f"report_{chat_id}",
    )

    # Launch Playwright coroutine
    from sf_bot import run_sf_bot
    state.task = asyncio.create_task(run_sf_bot(state, config, context))

    await update.message.reply_text(
        f"🚀 <b>Shakes &amp; Fortune inicializado</b>\n"
        f"🧙 Personaje: <b>{_character_label()}</b>\n"
        f"🎯 Objetivo: Infinito (AFK)\n"
        f"💻 Dispositivo: Playwright (Chromium)\n"
        f"🔔 Reportes: Cada 5 minutos",
        parse_mode="HTML",
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update.effective_chat.id):
        return
    state.running = False

    # Remove periodic jobs
    jobs = context.job_queue.get_jobs_by_name(f"report_{update.effective_chat.id}")
    for job in jobs:
        job.schedule_removal()

    # Wait for Playwright task
    if state.task and not state.task.done():
        try:
            await asyncio.wait_for(state.task, timeout=config["timing"]["stop_timeout"])
        except asyncio.TimeoutError:
            state.task.cancel()
            logger.warning("Playwright task did not stop in time; cancelled.")

    await update.message.reply_text(
        "🔕 <b>Notificaciones detenidas.</b>\n"
        "No recibirás más reportes cada 5 minutos.\n"
        "Envía /start para reactivarlas cuando quieras.",
        parse_mode="HTML",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_authorized(update.effective_chat.id):
        return
    await update.message.reply_text(
        f"📊 <b>Reporte instantáneo</b>\n\n"
        f"🧙 Personaje: {_character_label()}\n"
        f"⏱️ Tiempo Activo: {state.elapsed_minutes()} min\n"
        f"📺 Anuncios Vistos: {state.ads_watched}\n"
        f"🔄 Estado Actual: {state.current_status}",
        parse_mode="HTML",
    )


async def periodic_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=(
            f"🏛️ <b>Shakes &amp; Fortune — Estado</b>\n\n"
            f"🧙 Personaje: {_character_label()}\n"
            f"⏱️ Tiempo Activo: {state.elapsed_minutes()} min\n"
            f"📺 Anuncios Vistos: {state.ads_watched}\n"
            f"🔄 Estado Actual: {state.current_status}"
        ),
        parse_mode="HTML",
    )
