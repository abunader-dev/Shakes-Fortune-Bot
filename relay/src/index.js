/**
 * Shakes & Fortune — Telegram Relay Worker (Cloudflare Workers + KV)
 *
 * Allows multiple users to control their own local Shakes & Fortune bot
 * through a single shared Telegram bot (@shakes_fortune_bot) without ever
 * exposing the Telegram Bot Token to client machines.
 *
 * Required Worker Secrets (set via `wrangler secret put`):
 *   - TELEGRAM_TOKEN  : Bot token from @BotFather
 *   - WEBHOOK_SECRET  : Random secret used to validate Telegram webhook requests
 *
 * Required KV Binding:
 *   - RELAY_KV        : Cloudflare KV namespace
 */

const PAIR_TTL_SECONDS = 600; // 10 minutes
const CMD_TTL_SECONDS = 180;  // 3 minutes

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function randomHex(bytes = 24) {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, "0")).join("");
}

function randomSixDigitCode() {
  const arr = new Uint32Array(1);
  crypto.getRandomValues(arr);
  return String(100000 + (arr[0] % 900000));
}

function getBearerSecret(request) {
  const auth = request.headers.get("authorization") || "";
  if (!auth.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.slice(7).trim();
  return token.length >= 16 ? token : null;
}

async function sendTelegramMessage(env, chatId, text, parseMode = "HTML") {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: parseMode,
    }),
  });
  return resp.ok;
}

async function handlePairCreate(env) {
  const secret = randomHex(24);
  let code = randomSixDigitCode();

  // Avoid rare collisions
  for (let i = 0; i < 5; i++) {
    const existing = await env.RELAY_KV.get(`pair:${code}`);
    if (!existing) break;
    code = randomSixDigitCode();
  }

  await env.RELAY_KV.put(
    `pair:${code}`,
    JSON.stringify({ secret, created_at: Date.now() }),
    { expirationTtl: PAIR_TTL_SECONDS }
  );

  return jsonResponse({
    ok: true,
    code,
    secret,
    expires_in: PAIR_TTL_SECONDS,
  });
}

async function handlePairStatus(request, env) {
  const secret = getBearerSecret(request);
  if (!secret) return jsonResponse({ ok: false, error: "missing_secret" }, 401);

  const clientRaw = await env.RELAY_KV.get(`client:${secret}`);
  if (!clientRaw) {
    return jsonResponse({ ok: true, linked: false });
  }
  const client = JSON.parse(clientRaw);
  return jsonResponse({
    ok: true,
    linked: true,
    username: client.username || "",
    first_name: client.first_name || "",
  });
}

async function handlePoll(request, env) {
  const secret = getBearerSecret(request);
  if (!secret) return jsonResponse({ ok: false, error: "missing_secret" }, 401);

  const cmdRaw = await env.RELAY_KV.get(`cmd:${secret}`);
  if (cmdRaw) {
    await env.RELAY_KV.delete(`cmd:${secret}`);
    const cmdObj = JSON.parse(cmdRaw);
    return jsonResponse({ ok: true, linked: true, command: cmdObj.command });
  }

  const clientRaw = await env.RELAY_KV.get(`client:${secret}`);
  return jsonResponse({ ok: true, linked: Boolean(clientRaw), command: null });
}

async function handleNotify(request, env) {
  const secret = getBearerSecret(request);
  if (!secret) return jsonResponse({ ok: false, error: "missing_secret" }, 401);

  const clientRaw = await env.RELAY_KV.get(`client:${secret}`);
  if (!clientRaw) {
    return jsonResponse({ ok: false, error: "not_linked" }, 403);
  }
  const client = JSON.parse(clientRaw);

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ ok: false, error: "invalid_json" }, 400);
  }

  const text = String(body.text || "").trim();
  if (!text) return jsonResponse({ ok: false, error: "empty_text" }, 400);

  const parseMode = body.parse_mode || "HTML";
  const sent = await sendTelegramMessage(env, client.chat_id, text, parseMode);
  return jsonResponse({ ok: sent });
}

async function linkCodeToChat(env, code, chatId, fromUser) {
  const cleanCode = code.replace(/[^0-9]/g, "");
  if (cleanCode.length !== 6) {
    await sendTelegramMessage(
      env,
      chatId,
      "❌ El código debe tener 6 dígitos.\nEjemplo: <code>/vincular 482913</code>"
    );
    return;
  }

  const pairRaw = await env.RELAY_KV.get(`pair:${cleanCode}`);
  if (!pairRaw) {
    await sendTelegramMessage(
      env,
      chatId,
      "❌ Código inválido o expirado.\nGenerá uno nuevo desde <b>Shakes &amp; Fortune</b> en tu PC."
    );
    return;
  }

  const pair = JSON.parse(pairRaw);
  const newSecret = pair.secret;

  // Clean up any previous binding for this Telegram chat
  const oldChatRaw = await env.RELAY_KV.get(`chat:${chatId}`);
  if (oldChatRaw) {
    try {
      const oldChat = JSON.parse(oldChatRaw);
      if (oldChat.secret && oldChat.secret !== newSecret) {
        await env.RELAY_KV.delete(`client:${oldChat.secret}`);
      }
    } catch {
      // ignore malformed legacy value
    }
  }

  const meta = {
    chat_id: chatId,
    username: fromUser?.username || "",
    first_name: fromUser?.first_name || "",
    linked_at: Date.now(),
  };

  await Promise.all([
    env.RELAY_KV.put(`client:${newSecret}`, JSON.stringify(meta)),
    env.RELAY_KV.put(`chat:${chatId}`, JSON.stringify({ secret: newSecret, linked_at: Date.now() })),
    env.RELAY_KV.delete(`pair:${cleanCode}`),
  ]);

  await sendTelegramMessage(
    env,
    chatId,
    "✅ <b>¡PC vinculada con éxito!</b>\n\n" +
      "Ya podés controlar tu bot desde acá:\n" +
      "• /start — Iniciar el farmeo de anuncios\n" +
      "• /status — Ver estado y anuncios vistos\n" +
      "• /stop — Detener el bot\n" +
      "• /desvincular — Desconectar esta PC"
  );
}

async function enqueueCommandForChat(env, chatId, command, ackText) {
  const chatRaw = await env.RELAY_KV.get(`chat:${chatId}`);
  if (!chatRaw) {
    await sendTelegramMessage(
      env,
      chatId,
      "👋 <b>¡Bienvenido a Shakes &amp; Fortune!</b>\n\n" +
        "Todavía no vinculaste tu PC:\n" +
        "1. Abrí <b>ShakesFortune.bat</b> en tu computadora\n" +
        "2. Tocá <b>🤖 Vincular Telegram</b>\n" +
        "3. Tocá el botón para abrir este chat o mandame <code>/vincular CODIGO</code>"
    );
    return;
  }

  const { secret } = JSON.parse(chatRaw);
  await env.RELAY_KV.put(
    `cmd:${secret}`,
    JSON.stringify({ command, ts: Date.now() }),
    { expirationTtl: CMD_TTL_SECONDS }
  );

  if (ackText) {
    await sendTelegramMessage(env, chatId, ackText);
  }
}

async function handleTelegramWebhook(request, env) {
  // Validate Telegram webhook secret header
  const headerSecret = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (!env.WEBHOOK_SECRET || headerSecret !== env.WEBHOOK_SECRET) {
    return jsonResponse({ ok: false, error: "forbidden" }, 403);
  }

  let update;
  try {
    update = await request.json();
  } catch {
    return jsonResponse({ ok: true });
  }

  const message = update.message;
  if (!message || !message.chat || typeof message.text !== "string") {
    return jsonResponse({ ok: true });
  }

  const chatId = message.chat.id;
  const fromUser = message.from || {};
  const text = message.text.trim();
  const parts = text.split(/\s+/);
  const rawCmd = parts[0].toLowerCase().split("@")[0];
  const arg = parts.slice(1).join(" ").trim();

  if (rawCmd === "/vincular") {
    await linkCodeToChat(env, arg, chatId, fromUser);
  } else if (rawCmd === "/start" && arg) {
    // Deep link: https://t.me/shakes_fortune_bot?start=482913
    await linkCodeToChat(env, arg, chatId, fromUser);
  } else if (rawCmd === "/start") {
    await enqueueCommandForChat(env, chatId, "start", "⏳ Enviando <b>/start</b> a tu PC...");
  } else if (rawCmd === "/stop") {
    await enqueueCommandForChat(env, chatId, "stop", "⏳ Enviando <b>/stop</b> a tu PC...");
  } else if (rawCmd === "/status") {
    await enqueueCommandForChat(env, chatId, "status", null);
  } else if (rawCmd === "/desvincular") {
    const chatRaw = await env.RELAY_KV.get(`chat:${chatId}`);
    if (chatRaw) {
      const { secret } = JSON.parse(chatRaw);
      await Promise.all([
        env.RELAY_KV.delete(`chat:${chatId}`),
        env.RELAY_KV.delete(`client:${secret}`),
        env.RELAY_KV.delete(`cmd:${secret}`),
      ]);
      await sendTelegramMessage(env, chatId, "🔌 PC desvinculada. Podés volver a vincularla cuando quieras.");
    } else {
      await sendTelegramMessage(env, chatId, "ℹ️ No tenés ninguna PC vinculada actualmente.");
    }
  } else if (rawCmd === "/help" || rawCmd === "/ayuda") {
    await sendTelegramMessage(
      env,
      chatId,
      "🍀 <b>Shakes &amp; Fortune — Comandos</b>\n\n" +
        "• /vincular CODIGO — Vincular tu PC\n" +
        "• /start — Iniciar el bot en tu PC\n" +
        "• /status — Ver progreso actual\n" +
        "• /stop — Detener el bot\n" +
        "• /desvincular — Desconectar tu PC"
    );
  }

  return jsonResponse({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method.toUpperCase();

    if (method === "GET" && pathname === "/health") {
      return jsonResponse({ ok: true, service: "shakes-fortune-relay", bot: "@shakes_fortune_bot" });
    }
    if (method === "POST" && pathname === "/telegram") {
      return handleTelegramWebhook(request, env);
    }
    if (method === "POST" && pathname === "/api/pair/create") {
      return handlePairCreate(env);
    }
    if (method === "GET" && pathname === "/api/pair/status") {
      return handlePairStatus(request, env);
    }
    if (method === "GET" && pathname === "/api/poll") {
      return handlePoll(request, env);
    }
    if (method === "POST" && pathname === "/api/notify") {
      return handleNotify(request, env);
    }

    return jsonResponse({ ok: false, error: "not_found" }, 404);
  },
};
