"""
Shared configuration, multi-character profile management, Telegram token validation,
Chrome CDP helpers, and 1-click canvas calibration.
"""
import asyncio
import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Optional

import httpx
import yaml
from playwright.async_api import async_playwright

from sf_bot import DEFAULT_REL_COORDS, get_game_rect

CONFIG_PATH = "config.yaml"
EXAMPLE_PATH = "config.example.yaml"
STATE_PATH = "state.json"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"
DEFAULT_RELAY_URL = "https://shakes-fortune-relay.abunader-sf.workers.dev"
BOT_USERNAME = "shakes_fortune_bot"


def _default_config() -> dict:
    return {
        "character_name": "",
        "server_id": "",
        "server_url": "https://sfgame.net",
        "telegram_token": "",
        "owner_chat_id": 0,
        "headless": False,
        "relay": {
            "url": DEFAULT_RELAY_URL,
            "client_secret": "",
            "telegram_user": "",
        },
        "browser": {"use_existing_browser": True, "cdp_url": DEFAULT_CDP_URL},
        "active_profile": "",
        "profiles": [],
        "selectors": {
            "char_select_form": "#selectCharacterScene",
            "play_now_rel": {"rx": DEFAULT_REL_COORDS["play_now"][0], "ry": DEFAULT_REL_COORDS["play_now"][1]},
            "character_rel": {"rx": DEFAULT_REL_COORDS["character"][0], "ry": DEFAULT_REL_COORDS["character"][1]},
            "wheel_rel": {"rx": DEFAULT_REL_COORDS["wheel"][0], "ry": DEFAULT_REL_COORDS["wheel"][1]},
            "tv_rel": {"rx": DEFAULT_REL_COORDS["tv"][0], "ry": DEFAULT_REL_COORDS["tv"][1]},
            "ad_close_fallback_rel": {
                "rx": DEFAULT_REL_COORDS["ad_close_fallback"][0],
                "ry": DEFAULT_REL_COORDS["ad_close_fallback"][1],
            },
            "ad_container": "#ayetsdk_ad_container",
            "ad_wrapper": "#ayetsdk_content_wrapper",
            "video_element": "video#ayetsdk_content_element, video",
            "play_button": "#ayetsdk_play_button",
            "close_buttons": [
                "#ayetsdk_skipreward_button",
                '[id*="close"]',
                '[class*="close"]',
            ],
        },
        "timing": {
            "action_delay": 0.8,
            "ad_wait_max": 60,
            "poll_interval": 1.0,
            "report_interval": 300,
            "stop_timeout": 15,
            "tv_wait_max": 300,
        },
    }


def profile_id(name: str, server: str) -> str:
    return f"{name} ({server})" if server else name


def ensure_profiles_migrated(config: dict) -> dict:
    """Ensure config contains a valid `profiles` list synced with legacy fields."""
    profiles = config.get("profiles")
    if not isinstance(profiles, list):
        profiles = []
        config["profiles"] = profiles

    selectors = config.setdefault("selectors", {})
    for key, default_name in (
        ("play_now_rel", "play_now"),
        ("wheel_rel", "wheel"),
        ("tv_rel", "tv"),
        ("ad_close_fallback_rel", "ad_close_fallback"),
    ):
        if key not in selectors:
            drx, dry = DEFAULT_REL_COORDS[default_name]
            selectors[key] = {"rx": drx, "ry": dry}

    # Auto-migrate existing single-character config into the first profile
    if not profiles:
        legacy_name = str(config.get("character_name", "")).strip()
        legacy_server = str(config.get("server_id", "")).strip()
        if legacy_name and legacy_name not in ("NombreDeTuPersonaje", "NombreDetuPersonaje"):
            rel = selectors.get("character_rel")
            if not (isinstance(rel, dict) and "rx" in rel and "ry" in rel):
                drx, dry = DEFAULT_REL_COORDS["character"]
                rel = {"rx": drx, "ry": dry}
            profiles.append(
                {
                    "name": legacy_name,
                    "server": legacy_server or "EU30",
                    "character_rel": {"rx": float(rel["rx"]), "ry": float(rel["ry"])},
                    "calibrated": True,
                }
            )
            config["active_profile"] = profile_id(legacy_name, legacy_server or "EU30")

    if profiles:
        sync_active_profile(config)
    return config


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load config.yaml (or seed from config.example.yaml/defaults) with profiles migrated."""
    base = _default_config()
    loaded = None
    for candidate in (path, EXAMPLE_PATH):
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    loaded = data
                    break

    if loaded:
        for k, v in loaded.items():
            if isinstance(v, dict) and isinstance(base.get(k), dict):
                base[k].update(v)
            else:
                base[k] = v

    return ensure_profiles_migrated(base)


def save_config(config: dict, path: str = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


def get_active_profile_index(config: dict) -> int:
    profiles = config.get("profiles", [])
    if not profiles:
        return -1
    active = config.get("active_profile", "")
    for idx, prof in enumerate(profiles):
        if profile_id(prof.get("name", ""), prof.get("server", "")) == active:
            return idx
    return 0


def sync_active_profile(config: dict) -> Optional[dict]:
    """Copy active profile settings into top-level fields used by sf_bot.py."""
    profiles = config.get("profiles", [])
    if not profiles:
        config["active_profile"] = ""
        return None

    idx = get_active_profile_index(config)
    prof = profiles[idx]
    config["active_profile"] = profile_id(prof.get("name", ""), prof.get("server", ""))
    config["character_name"] = prof.get("name", "")
    config["server_id"] = prof.get("server", "")
    rel = prof.get("character_rel")
    if isinstance(rel, dict) and "rx" in rel and "ry" in rel:
        config.setdefault("selectors", {})["character_rel"] = {
            "rx": round(float(rel["rx"]), 4),
            "ry": round(float(rel["ry"]), 4),
        }
    return prof


def set_active_profile(config: dict, index: int) -> Optional[dict]:
    profiles = config.get("profiles", [])
    if 0 <= index < len(profiles):
        prof = profiles[index]
        config["active_profile"] = profile_id(prof.get("name", ""), prof.get("server", ""))
        return sync_active_profile(config)
    return None


def upsert_profile(
    config: dict,
    name: str,
    server: str,
    character_rel: Optional[dict] = None,
    *,
    calibrated: Optional[bool] = None,
    edit_index: Optional[int] = None,
) -> dict:
    """Create or update a character profile and make it active."""
    profiles = config.setdefault("profiles", [])
    name = name.strip()
    server = server.strip().upper()

    if character_rel is None:
        drx, dry = DEFAULT_REL_COORDS["character"]
        character_rel = {"rx": drx, "ry": dry}

    entry = {
        "name": name,
        "server": server,
        "character_rel": {
            "rx": round(float(character_rel["rx"]), 4),
            "ry": round(float(character_rel["ry"]), 4),
        },
        "calibrated": bool(calibrated) if calibrated is not None else False,
    }

    if edit_index is not None and 0 <= edit_index < len(profiles):
        profiles[edit_index] = entry
    else:
        # Update matching name+server if it already exists
        target_id = profile_id(name, server)
        replaced = False
        for i, existing in enumerate(profiles):
            if profile_id(existing.get("name", ""), existing.get("server", "")) == target_id:
                profiles[i] = entry
                replaced = True
                break
        if not replaced:
            profiles.append(entry)

    config["active_profile"] = profile_id(name, server)
    sync_active_profile(config)
    return entry


def delete_profile(config: dict, index: int) -> None:
    profiles = config.get("profiles", [])
    if 0 <= index < len(profiles):
        profiles.pop(index)
        sync_active_profile(config)


def has_valid_token_format(config: dict) -> bool:
    token = str(config.get("telegram_token", "")).strip()
    return bool(token) and ":" in token and "PON_TU_TOKEN" not in token


def get_relay_url(config: dict) -> str:
    relay = config.get("relay") or {}
    return str(relay.get("url") or DEFAULT_RELAY_URL).strip().rstrip("/")


def is_relay_linked(config: dict) -> bool:
    relay = config.get("relay") or {}
    return bool(str(relay.get("client_secret", "")).strip())


def relay_create_pair(relay_url: str = DEFAULT_RELAY_URL) -> dict:
    """Request a 6-digit pairing code and client secret from the shared relay."""
    url = f"{relay_url.rstrip('/')}/api/pair/create"
    resp = httpx.post(url, json={}, timeout=10.0)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError("Relay rechazó la solicitud de vinculación.")
    return data


def relay_check_pair_status(relay_url: str, secret: str) -> dict:
    """Poll whether the user completed /vincular in @shakes_fortune_bot."""
    url = f"{relay_url.rstrip('/')}/api/pair/status"
    resp = httpx.get(url, headers={"Authorization": f"Bearer {secret}"}, timeout=8.0)
    resp.raise_for_status()
    return resp.json()


def validate_telegram_token(token: str) -> Optional[dict]:
    """Validate a Telegram Bot API token via getMe and return bot metadata."""
    token = token.strip()
    if not token or ":" not in token:
        return None
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            if payload.get("ok"):
                return payload.get("result")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
    return None


def read_bot_stats(path: str = STATE_PATH) -> dict:
    if not os.path.exists(path):
        return {"ads_watched": 0, "current_status": "Detenido"}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"ads_watched": 0, "current_status": "Detenido"}


def is_cdp_ready(cdp_url: str = DEFAULT_CDP_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def has_sfgame_tab(cdp_url: str = DEFAULT_CDP_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{cdp_url}/json", timeout=1.5) as resp:
            tabs = json.loads(resp.read().decode("utf-8"))
            return any("sfgame.net" in str(t.get("url", "")) for t in tabs if t.get("type") == "page")
    except Exception:
        return False


def find_chrome() -> Optional[str]:
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LocalAppData", ""), "Google", "Chrome", "Application", "chrome.exe"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def ensure_chrome_running(cdp_url: str = DEFAULT_CDP_URL) -> bool:
    """Return True if Chrome was already running, False if newly launched."""
    if is_cdp_ready(cdp_url):
        return True

    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("No se encontro Google Chrome instalado.")

    profile_dir = os.path.abspath("chrome-profile")
    subprocess.Popen(
        [
            chrome,
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "https://sfgame.net",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return False


async def capture_character_click(
    cdp_url: str = DEFAULT_CDP_URL,
    label: str = "",
    timeout_seconds: int = 120,
) -> dict:
    """Attach to the open sfgame.net tab and capture 1 click on the user's character card."""
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        if not browser.contexts:
            raise RuntimeError("Chrome no tiene ningun contexto abierto.")
        ctx = browser.contexts[0]
        page = next((pg for pg in ctx.pages if "sfgame.net" in pg.url), None)
        if page is None:
            raise RuntimeError("No se encontro una pestana con sfgame.net abierta en Chrome.")

        await page.bring_to_front()
        await page.wait_for_selector("#canvas", state="visible", timeout=30000)

        gx, gy, gw, gh = await get_game_rect(page)
        banner_text = (
            f"Shakes & Fortune — Haz CLIC UNA VEZ sobre {label}"
            if label
            else "Shakes & Fortune — Haz CLIC UNA VEZ sobre la tarjeta de tu personaje"
        )

        click_pos = await asyncio.wait_for(
            page.evaluate(
                """([gx, gy, gw, gh, bannerText]) => new Promise((resolve) => {
                    const oldBanner = document.getElementById('sf-bot-calib-banner');
                    if (oldBanner) oldBanner.remove();

                    const banner = document.createElement('div');
                    banner.id = 'sf-bot-calib-banner';
                    banner.textContent = bannerText;
                    Object.assign(banner.style, {
                        position: 'fixed',
                        top: '14px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        zIndex: '2147483647',
                        background: 'rgba(7, 19, 28, 0.95)',
                        color: '#f5c542',
                        border: '2px solid #f5c542',
                        borderRadius: '10px',
                        padding: '12px 24px',
                        fontFamily: 'Segoe UI, sans-serif',
                        fontSize: '16px',
                        fontWeight: '700',
                        pointerEvents: 'none',
                        boxShadow: '0 6px 24px rgba(0,0,0,0.7)',
                    });
                    document.body.appendChild(banner);

                    function onPointerDown(e) {
                        const rx = (e.clientX - gx) / gw;
                        const ry = (e.clientY - gy) / gh;
                        if (rx < 0 || rx > 1 || ry < 0 || ry > 1) {
                            return;
                        }
                        window.removeEventListener('pointerdown', onPointerDown, true);
                        banner.remove();
                        resolve({x: e.clientX, y: e.clientY, rx, ry});
                    }

                    window.addEventListener('pointerdown', onPointerDown, true);
                })""",
                [gx, gy, gw, gh, banner_text],
            ),
            timeout=timeout_seconds,
        )

        await browser.close()
        return {
            "rx": round(float(click_pos["rx"]), 4),
            "ry": round(float(click_pos["ry"]), 4),
        }
