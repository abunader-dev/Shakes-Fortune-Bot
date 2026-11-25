import asyncio
import logging
import os
import json
import time
from io import BytesIO
from typing import Optional
from PIL import Image
from playwright.async_api import (
    async_playwright,
    Page,
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
)

from bot_state import BotState

logger = logging.getLogger(__name__)


class SessionDroppedError(Exception):
    """Raised when the game session drops to the character selection screen."""
    pass


# Unity WebGL renders Shakes & Fidget in a centered 16:9 viewport inside #canvas.
GAME_ASPECT_RATIO = 16.0 / 9.0

# Resolution-independent default click targets inside the 16:9 game area (0.0..1.0).
DEFAULT_REL_COORDS: dict[str, tuple[float, float]] = {
    "play_now": (0.5000, 0.9524),
    "character": (0.3500, 0.5164),
    "wheel": (0.1851, 0.5132),
    "tv": (0.3333, 0.1323),
    "ad_close_fallback": (0.8851, 0.1312),
}

# Relative interior region of the Character Selection modal inside the 16:9 game area.
CHAR_SELECT_REL_BOX: tuple[float, float, float, float] = (0.2321, 0.2116, 0.7381, 0.6667)


def compute_game_rect(
    container_x: float,
    container_y: float,
    container_w: float,
    container_h: float,
    aspect: float = GAME_ASPECT_RATIO,
) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) of the centered 16:9 game area inside a container."""
    if container_w <= 0 or container_h <= 0:
        return (container_x, container_y, max(container_w, 1.0), max(container_h, 1.0))

    if (container_w / container_h) > aspect:
        game_h = container_h
        game_w = container_h * aspect
        game_x = container_x + (container_w - game_w) / 2.0
        game_y = container_y
    else:
        game_w = container_w
        game_h = container_w / aspect
        game_x = container_x
        game_y = container_y + (container_h - game_h) / 2.0

    return (game_x, game_y, game_w, game_h)


async def get_game_rect(page: Page) -> tuple[float, float, float, float]:
    """Return (x, y, width, height) of the active 16:9 game viewport in CSS pixels."""
    rect = await page.evaluate(
        """() => {
            const c = document.querySelector('#canvas');
            if (c) {
                const r = c.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    return {x: r.left, y: r.top, w: r.width, h: r.height};
                }
            }
            return {x: 0, y: 0, w: window.innerWidth, h: window.innerHeight};
        }"""
    )
    return compute_game_rect(rect["x"], rect["y"], rect["w"], rect["h"])


async def resolve_game_point(
    page: Page,
    config: dict,
    rel_key: str,
    default_name: str,
) -> tuple[float, float]:
    """Convert a relative target coordinate (rx, ry) into CSS pixels for any screen size."""
    selectors = config.get("selectors", {})
    rel_cfg = selectors.get(rel_key)
    if isinstance(rel_cfg, dict) and "rx" in rel_cfg and "ry" in rel_cfg:
        rx, ry = float(rel_cfg["rx"]), float(rel_cfg["ry"])
    else:
        rx, ry = DEFAULT_REL_COORDS[default_name]

    gx, gy, gw, gh = await get_game_rect(page)
    return (gx + rx * gw, gy + ry * gh)


def save_state(state: BotState, path: str = "state.json") -> None:
    try:
        data = {
            "ads_watched": state.ads_watched,
            "lucky_coins": state.lucky_coins,
            "current_status": state.current_status,
            "consecutive_errors": state.consecutive_errors,
            "consecutive_session_recoveries": state.consecutive_session_recoveries,
            "start_time": state.start_time,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving state to {path}: {e}")


def load_state(state: BotState, path: str = "state.json") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            state.ads_watched = data.get("ads_watched", 0)
            state.lucky_coins = data.get("lucky_coins", 0)
    except Exception as e:
        logger.error(f"Error loading state from {path}: {e}")


async def is_char_select_visible(page: Page, config: dict) -> bool:
    """Detecta si el juego está en el selector de personaje.

    El selector muestra un modal DOM que cubre el centro de la pantalla con un
    fondo azul-oscuro muy característico (r<25, g<45, 25<b<60).
    En ese mismo área, la pantalla del juego en sesión tiene colores cálidos
    (marrón, dorado, verde) propios del juego.

    Umbrales calibrados sobre capturas reales:
      - Selector: ~84 % píxeles azul-oscuro en zona (510,200)→(1360,630)
      - En juego:  ~0 %  píxeles azul-oscuro en la misma zona
    Umbral de corte: 30 % (> 30 % → selector visible).
    """
    try:
        # Chequeo rápido por URL
        if "login" in page.url.lower():
            return True

        # Chequeo DOM (por si el juego expone algún elemento)
        char_form = config.get("selectors", {}).get("char_select_form", "#selectCharacterScene")
        el = await page.query_selector(char_form)
        if el and await el.is_visible():
            return True

        # Visual detection: the character-selection modal fills the center of the
        # 16:9 game area with a distinctive dark navy-blue background.
        screenshot = await page.screenshot()
        image = Image.open(BytesIO(screenshot)).convert("RGB")
        img_w, img_h = image.size
        gx, gy, gw, gh = compute_game_rect(0.0, 0.0, float(img_w), float(img_h))
        rx1, ry1, rx2, ry2 = CHAR_SELECT_REL_BOX
        zone = image.crop(
            (
                int(gx + rx1 * gw),
                int(gy + ry1 * gh),
                int(gx + rx2 * gw),
                int(gy + ry2 * gh),
            )
        )
        pixels = list(zone.getdata())
        total = len(pixels)
        if total == 0:
            return False
        modal_bg = sum(
            1 for r, g, b in pixels
            if r < 25 and g < 45 and 25 < b < 60
        )
        return (modal_bg / total) > 0.30

    except Exception:
        pass
    return False


async def select_character(
    page: Page,
    config: dict,
    state: BotState,
    *,
    click_play_now: bool = False,
) -> None:
    """Enter the configured character from the canvas-based selection screens."""
    state.current_status = "Entrando al juego"
    char_label = config.get("character_name", "character")
    server_label = config.get("server_id", "")
    target_desc = f"{char_label} ({server_label})" if server_label else char_label
    logger.info("Selecting %s through the game canvas.", target_desc)

    if click_play_now:
        px, py = await resolve_game_point(page, config, "play_now_rel", "play_now")
        await page.mouse.click(px, py)
        await asyncio.sleep(2.0)

    cx, cy = await resolve_game_point(page, config, "character_rel", "character")
    await page.mouse.click(cx, cy)
    await asyncio.sleep(3.0)
    if await is_char_select_visible(page, config):
        logger.warning("Character selection is still visible after clicking %s at (%.1f, %.1f).", target_desc, cx, cy)
    else:
        logger.info("Character session confirmed after clicking %s.", target_desc)


async def navigate_to_wheel(page: Page, config: dict, state: BotState) -> None:
    """Navigates to Dr. Abawuwu (Wheel of Fortune) using resolution-independent coordinates."""
    state.current_status = "Navegando a la ruleta"
    logger.info("Navigating to wheel...")

    if await is_char_select_visible(page, config):
        raise SessionDroppedError("Cannot navigate to the wheel without an active character session.")

    wx, wy = await resolve_game_point(page, config, "wheel_rel", "wheel")
    await page.mouse.click(wx, wy)
    await asyncio.sleep(2.0)


async def wait_for_tv_or_session_drop(page: Page, config: dict, state: BotState) -> None:
    """Click the Flying TV repeatedly until an ad starts."""
    state.current_status = "Buscando TV"
    logger.info("Waiting for Flying TV...")

    tv_wait_max = config.get("timing", {}).get("tv_wait_max", 30)
    retry_every = 4.0
    deadline = time.monotonic() + tv_wait_max
    attempt = 0

    while state.running and time.monotonic() < deadline:
        if await is_char_select_visible(page, config):
            raise SessionDroppedError("Session dropped while waiting for the Flying TV.")

        attempt += 1
        state.current_status = f"Buscando TV (intento {attempt})"
        tv_x, tv_y = await resolve_game_point(page, config, "tv_rel", "tv")
        try:
            await page.mouse.click(tv_x, tv_y)
        except Exception as exc:
            raise RuntimeError(f"Could not click Flying TV at ({tv_x:.1f}, {tv_y:.1f}).") from exc

        # Esperar hasta 'retry_every' s a que el anuncio arranque.
        t0 = time.monotonic()
        while time.monotonic() - t0 < retry_every:
            await asyncio.sleep(0.5)
            if await _ad_started(page):
                logger.info(f"Ad started after {attempt} TV click(s).")
                await asyncio.sleep(1.0)
                return

    if not state.running:
        return
    raise TimeoutError(f"Flying TV did not appear / ad did not start within {tv_wait_max}s.")


async def click_tv(page: Page, config: dict, state: BotState) -> None:
    """Backward-compatible name for the manual single-cycle test."""
    await wait_for_tv_or_session_drop(page, config, state)


async def _reward_granted_visible(page: Page) -> bool:
    """True solo si 'Reward granted' está realmente visible (opacidad, visibilidad y no tapado)."""
    for frame in page.frames:
        try:
            loc = frame.get_by_text("Reward granted").first
            if not await loc.is_visible():
                continue
            real = await loc.evaluate(
                """el => {
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) return false;
                    let n = el;
                    while (n && n.nodeType === 1) {
                        const s = getComputedStyle(n);
                        if (parseFloat(s.opacity) < 0.9 || s.visibility === 'hidden' || s.display === 'none') return false;
                        n = n.parentElement;
                    }
                    const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                    return !!top && (el === top || el.contains(top) || top.contains(el));
                }""",
                timeout=500,
            )
            if real:
                return True
        except Exception:
            continue
    return False


async def _ad_started(page: Page) -> bool:
    """True si el SDK de AyeT o el modal 'Video Box' ya están visibles."""
    for frame in page.frames:
        try:
            if await frame.locator("#ayetsdk_ad_container").first.is_visible():
                return True
        except Exception:
            pass
        try:
            if await frame.get_by_text("Video Box").first.is_visible():
                return True
        except Exception:
            pass
    return False


async def _ad_video_state(page: Page) -> Optional[dict]:
    """Estado del <video> del anuncio, o None si no se encuentra."""
    try:
        return await page.evaluate(
            """() => {
                const v = document.querySelector('video#ayetsdk_content_element')
                    || document.querySelector('#ayetsdk_ad_container video')
                    || document.querySelector('video');
                if (!v) return null;
                return {paused: v.paused, ended: v.ended, t: v.currentTime, d: v.duration || 0};
            }"""
        )
    except Exception:
        return None


async def wait_for_ad_end_or_session_drop(page: Page, config: dict, state: BotState) -> None:
    """
    Espera pasivamente a que termine el anuncio. Solo hace clic en Play de AyeT
    si el video está realmente en pausa sin empezar. Termina cuando 'Reward granted'
    está confirmado y el video ya no se reproduce.
    """
    state.current_status = "Viendo anuncio"
    logger.info("Waiting for ad end...")

    play_selector = "#ayetsdk_play_button"
    max_wait = config.get("timing", {}).get("ad_wait_max", 60) + 60

    async def wait_for_reward() -> None:
        play_clicked = False
        seen_reward = 0
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            video = await _ad_video_state(page)

            if (not play_clicked and video and video["paused"]
                    and not video["ended"] and video["t"] == 0):
                try:
                    play_btn = page.locator(play_selector)
                    if await play_btn.is_visible():
                        logger.info("Video paused at 0s; clicking AyeT play button.")
                        await play_btn.click()
                        play_clicked = True
                except Exception as e:
                    logger.debug(f"Play button error: {e}")

            playing = bool(video) and not video["paused"] and not video["ended"]

            if await _reward_granted_visible(page):
                seen_reward += 1
                if seen_reward >= 2 and (not playing or seen_reward >= 6):
                    logger.info("Ad finished: 'Reward granted' confirmed.")
                    return
            else:
                seen_reward = 0

            await asyncio.sleep(1.0)

        raise TimeoutError("Ad did not finish: 'Reward granted' not confirmed in time.")

    async def monitor_session_drop() -> None:
        while True:
            await asyncio.sleep(1.0)
            if await is_char_select_visible(page, config):
                logger.error("Session drop detected during ad!")
                raise SessionDroppedError("Session dropped to character selection.")

    task_ad = asyncio.create_task(wait_for_reward())
    task_session = asyncio.create_task(monitor_session_drop())

    done, pending = await asyncio.wait(
        [task_ad, task_session],
        return_when=asyncio.FIRST_COMPLETED,
    )

    for t in pending:
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass

    for t in done:
        exc = t.exception()
        if exc:
            raise exc


async def close_ad_if_needed(page: Page, config: dict, state: BotState) -> None:
    """Cierra el modal del anuncio solo después de confirmar 'Reward granted'.

    Orden de intentos:
      1. Selector primario del SDK (ayetsdk_skipreward_button) — viene del config.
      2. Selectores adicionales del config (close_buttons).
      3. Búsqueda genérica de aria-label y texto de cierre.
      4. Fallback: clic nativo en la coordenada X del viewport.
    """
    state.current_status = "Cerrando anuncio"
    logger.info("Closing ad modal...")

    try:
        await page.bring_to_front()
    except Exception:
        pass

    # Guardia de seguridad: no cerrar si todavía no hay recompensa confirmada.
    if not await _reward_granted_visible(page):
        raise TimeoutError("Refusing to close ad: 'Reward granted' is not visible yet.")

    await asyncio.sleep(1.5)  # deja que el SDK termine de renderizar el botón

    # Selectores priorizados: primero los del SDK de AyeT, luego genéricos.
    sdk_primary = "#ayetsdk_skipreward_button"
    config_extras: list[str] = config.get("selectors", {}).get("close_buttons", [])
    generic_selectors = [
        '[aria-label*="close" i]',
        'text="✖"',
        'text="✕"',
        'text="×"',
        'text="X"',
    ]
    # Deduplicar manteniendo orden: SDK → config → genéricos
    all_selectors = [sdk_primary] + [
        s for s in config_extras if s != sdk_primary
    ] + [
        s for s in generic_selectors if s not in config_extras and s != sdk_primary
    ]

    for attempt in range(1, 4):
        clicked = False

        # Buscar en todos los frames (el SDK puede estar en un iframe).
        for selector in all_selectors:
            for frame in page.frames:
                try:
                    el = await frame.wait_for_selector(selector, state="visible", timeout=800)
                    if el:
                        await el.click()
                        clicked = True
                        logger.info(f"Clicked ad close button via DOM [{frame.name or 'main'}]: {selector}")
                        break
                except Exception:
                    continue
            if clicked:
                break

        # Fallback: native click in the top-right corner of the ad modal.
        if not clicked:
            fx, fy = await resolve_game_point(
                page, config, "ad_close_fallback_rel", "ad_close_fallback"
            )
            logger.info("Close button not found in DOM; native click at (%.1f, %.1f).", fx, fy)
            await page.mouse.click(fx, fy)

        await asyncio.sleep(1.0)

        # Verificar que el modal ya se fue (ya no hay "Reward granted" visible).
        if not await _reward_granted_visible(page):
            logger.info("Ad modal closed successfully.")
            await asyncio.sleep(0.5)
            return

        logger.warning(f"Ad modal still open after attempt {attempt}.")

    raise RuntimeError("Ad modal did not close after 3 attempts.")


async def run_sf_bot(state: BotState, config: dict, context) -> None:
    """Main bot loop controlling Playwright."""
    logger.info("Starting run_sf_bot...")
    load_state(state)

    async with async_playwright() as p:
        browser_config = config.get("browser", {})
        use_existing_browser = browser_config.get("use_existing_browser", False)
        owns_browser = not use_existing_browser

        if use_existing_browser:
            cdp_url = browser_config.get("cdp_url", "http://127.0.0.1:9222")
            logger.info("Connecting to the user-managed Chrome browser at %s", cdp_url)
            browser = await p.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                raise RuntimeError("Chrome has no available browser context.")
            browser_context = browser.contexts[0]
            page = next(
                (open_page for open_page in browser_context.pages if "sfgame.net" in open_page.url),
                None,
            )
            if page is None:
                raise RuntimeError(
                    "Open sfgame.net in Chrome and leave the game ready before using /start."
                )
        else:
            browser = await p.chromium.launch(
                headless=config.get("headless", False)
            )

            auth_file = "auth.json"
            storage_state = auth_file if os.path.exists(auth_file) else None
            browser_context = await browser.new_context(
                storage_state=storage_state,
                viewport={"width": 1920, "height": 945}
            )
            page = await browser_context.new_page()

        server_url = config.get("server_url", "https://sfgame.net")

        async def _close_popup(popup) -> None:
            try:
                await popup.close()
                logger.info("Closed ad popup tab.")
            except Exception:
                pass

        page.on("popup", lambda popup: asyncio.create_task(_close_popup(popup)))

        try:
            state.current_status = "Cargando juego..."
            if not use_existing_browser:
                logger.info(f"Navigating to {server_url}...")
                await page.goto(server_url, wait_until="networkidle", timeout=60000)

            # Wait for canvas to load
            await page.wait_for_selector("#canvas", state="visible", timeout=30000)
            await asyncio.sleep(4.0)

            if use_existing_browser:
                if await is_char_select_visible(page, config):
                    await select_character(page, config, state)
                else:
                    logger.info("An active character session is already open.")
            else:
                await select_character(page, config, state, click_play_now=True)

            # Main loop
            while state.running:
                try:
                    # Check for session drop
                    if await is_char_select_visible(page, config):
                        logger.warning("Character selection detected on cycle start.")
                        raise SessionDroppedError("Session dropped.")

                    # 1. Navigate to Wheel
                    await navigate_to_wheel(page, config, state)

                    # 2. Click Flying TV
                    await wait_for_tv_or_session_drop(page, config, state)

                    # 3. Wait for Ad End with session drop monitor
                    await wait_for_ad_end_or_session_drop(page, config, state)

                    # 4. Close Ad
                    await close_ad_if_needed(page, config, state)

                    # 5. Update counts
                    state.ads_watched += 1
                    state.current_status = "Anuncio completado"
                    save_state(state)
                    state.consecutive_errors = 0
                    state.consecutive_session_recoveries = 0
                    logger.info(f"Ad watched successfully! Total: {state.ads_watched}")

                    # Wait before next cycle
                    delay = config.get("timing", {}).get("action_delay", 1.0)
                    await asyncio.sleep(delay)

                except SessionDroppedError as sde:
                    logger.error(f"Session error: {sde}")
                    state.consecutive_session_recoveries += 1
                    state.last_error = str(sde)
                    state.current_status = "Sesión perdida"
                    if state.consecutive_session_recoveries >= 3:
                        state.running = False
                        state.current_status = "Detenido por 3 caídas consecutivas"
                        logger.error("Stopping bot due to 3 consecutive session drops.")
                        continue

                    await select_character(page, config, state)
                    continue

                except Exception as exc:
                    state.consecutive_errors += 1
                    state.last_error = str(exc)
                    logger.exception(f"Cycle failed: {exc}")
                    if state.consecutive_errors >= 5:
                        state.running = False
                        state.current_status = "Detenido por 5 errores consecutivos"
                        continue
                    state.current_status = f"Error, reintentando ({state.consecutive_errors}/5)"
                    await asyncio.sleep(3.0)
                    continue

        except asyncio.CancelledError:
            logger.info("run_sf_bot task was cancelled.")
        except Exception as e:
            logger.exception(f"Unexpected error in run_sf_bot: {e}")
            state.last_error = str(e)
            state.consecutive_errors += 1
        finally:
            state.current_status = "Detenido"
            save_state(state)
            if owns_browser:
                await browser_context.close()
                await browser.close()
                logger.info("Playwright browser closed cleanly.")
            else:
                logger.info("Disconnected from the user-managed Chrome browser.")

