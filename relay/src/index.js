/**
 * Shakes & Fortune — Telegram Relay Worker (Cloudflare Workers + D1 SQLite)
 *
 * Uses strongly consistent Cloudflare D1 so pairing codes and /start /stop /status
 * commands are visible to client PCs immediately (zero 60s KV negative caching).
 *
 * Required Worker Secrets (set via `wrangler secret put`):
 *   - TELEGRAM_TOKEN  : Bot token from @BotFather
 *   - WEBHOOK_SECRET  : Random secret used to validate Telegram webhook requests
 *
 * Required D1 Binding:
 *   - RELAY_DB        : Cloudflare D1 database (shakes-fortune-db)
 */

const PAIR_TTL_MS = 600 * 1000; // 10 minutes
const CMD_TTL_MS = 180 * 1000;  // 3 minutes

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

async function sendTelegramMessage(env, chatId, text, parseMode = "HTML", extra = {}) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`;
  const resp = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      chat_id: chatId,
      text,
      parse_mode: parseMode,
      ...extra,
    }),
  });
  return resp.ok;
}

async function handlePairCreate(env) {
  const now = Date.now();
  const expiresAt = now + PAIR_TTL_MS;
  const secret = randomHex(24);
  let code = randomSixDigitCode();

  // Opportunistic cleanup of expired pairing codes
  await env.RELAY_DB.prepare("DELETE FROM pairs WHERE expires_at < ?").bind(now).run();

  for (let i = 0; i < 5; i++) {
    const existing = await env.RELAY_DB.prepare("SELECT code FROM pairs WHERE code = ?")
      .bind(code)
      .first();
    if (!existing) break;
    code = randomSixDigitCode();
  }

  await env.RELAY_DB.prepare(
    "INSERT OR REPLACE INTO pairs (code, secret, expires_at) VALUES (?, ?, ?)"
  )
    .bind(code, secret, expiresAt)
    .run();

  return jsonResponse({
    ok: true,
    code,
    secret,
    expires_in: Math.floor(PAIR_TTL_MS / 1000),
  });
}

async function handlePairStatus(request, env) {
  const secret = getBearerSecret(request);
  if (!secret) return jsonResponse({ ok: false, error: "missing_secret" }, 401);

  const client = await env.RELAY_DB.prepare(
    "SELECT chat_id, username, first_name FROM clients WHERE secret = ?"
  )
    .bind(secret)
    .first();

  if (!client) {
    return jsonResponse({ ok: true, linked: false });
  }
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

  const now = Date.now();
  const cmdRow = await env.RELAY_DB.prepare(
    "SELECT command, expires_at FROM commands WHERE secret = ?"
  )
    .bind(secret)
    .first();

  if (cmdRow) {
    await env.RELAY_DB.prepare("DELETE FROM commands WHERE secret = ?").bind(secret).run();
    if (cmdRow.expires_at >= now) {
      return jsonResponse({ ok: true, linked: true, command: cmdRow.command });
    }
  }

  const client = await env.RELAY_DB.prepare("SELECT secret FROM clients WHERE secret = ?")
    .bind(secret)
    .first();
  return jsonResponse({ ok: true, linked: Boolean(client), command: null });
}

async function handleNotify(request, env) {
  const secret = getBearerSecret(request);
  if (!secret) return jsonResponse({ ok: false, error: "missing_secret" }, 401);

  const client = await env.RELAY_DB.prepare("SELECT chat_id FROM clients WHERE secret = ?")
    .bind(secret)
    .first();
  if (!client) {
    return jsonResponse({ ok: false, error: "not_linked" }, 403);
  }

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

  const now = Date.now();
  const pair = await env.RELAY_DB.prepare(
    "SELECT secret, expires_at FROM pairs WHERE code = ?"
  )
    .bind(cleanCode)
    .first();

  if (!pair || pair.expires_at < now) {
    await sendTelegramMessage(
      env,
      chatId,
      "❌ Código inválido o expirado.\nGenera uno nuevo desde <b>Shakes &amp; Fortune 🍀</b> en tu computadora."
    );
    return;
  }

  const newSecret = pair.secret;
  const username = fromUser?.username || "";
  const firstName = fromUser?.first_name || "";

  // Atomically replace any previous binding for this chat_id and clear pending pairing state
  await env.RELAY_DB.batch([
    env.RELAY_DB.prepare("DELETE FROM commands WHERE secret IN (SELECT secret FROM clients WHERE chat_id = ?)").bind(chatId),
    env.RELAY_DB.prepare("DELETE FROM clients WHERE chat_id = ?").bind(chatId),
    env.RELAY_DB.prepare(
      "INSERT OR REPLACE INTO clients (secret, chat_id, username, first_name, linked_at) VALUES (?, ?, ?, ?, ?)"
    ).bind(newSecret, chatId, username, firstName, now),
    env.RELAY_DB.prepare("DELETE FROM pairs WHERE code = ?").bind(cleanCode),
    env.RELAY_DB.prepare("DELETE FROM awaiting_pair WHERE chat_id = ?").bind(chatId),
  ]);

  await sendTelegramMessage(
    env,
    chatId,
    "✅ <b>¡PC vinculada con éxito!</b>\n\n" +
      "Ya puedes controlar tu bot desde aquí:\n\n" +
      "• /start — Iniciar el farmeo de anuncios\n" +
      "• /status — Ver estado y anuncios vistos\n" +
      "• /stop — Detener el proceso del bot\n" +
      "• /desvincular — Desconectar esta PC"
  );
}

async function enqueueCommandForChat(env, chatId, command, ackText) {
  const client = await env.RELAY_DB.prepare("SELECT secret FROM clients WHERE chat_id = ?")
    .bind(chatId)
    .first();

  if (!client) {
    await env.RELAY_DB.prepare(
      "INSERT OR REPLACE INTO awaiting_pair (chat_id, expires_at) VALUES (?, ?)"
    )
      .bind(chatId, Date.now() + PAIR_TTL_MS)
      .run();

    await sendTelegramMessage(
      env,
      chatId,
      "🍀 <b>¡Bienvenido a Shakes &amp; Fortune!</b>\n\n" +
        "Todavía no has vinculado tu PC, para conectarla:\n\n" +
        "1. Abre <b>ShakesFortune.bat</b> en tu PC\n" +
        "2. Haz clic en <b>🍀 Vincular Telegram</b>\n" +
        "3. Toca el botón verde en la app o <b>escribe aquí /vincular, seguido del código de 6 dígitos</b>"
    );
    return;
  }

  await env.RELAY_DB.prepare(
    "INSERT OR REPLACE INTO commands (secret, command, expires_at) VALUES (?, ?, ?)"
  )
    .bind(client.secret, command, Date.now() + CMD_TTL_MS)
    .run();

  if (ackText) {
    await sendTelegramMessage(env, chatId, ackText);
  }
}

async function handleTelegramWebhook(request, env) {
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
    if (!arg) {
      await env.RELAY_DB.prepare(
        "INSERT OR REPLACE INTO awaiting_pair (chat_id, expires_at) VALUES (?, ?)"
      )
        .bind(chatId, Date.now() + PAIR_TTL_MS)
        .run();

      await sendTelegramMessage(
        env,
        chatId,
        "🔑 <b>Escribe ahora tu código de 6 dígitos</b>\n\n" +
          "<i>(Es el código que aparece al hacer clic en '🍀 Vincular Telegram' en Shakes &amp; Fortune)</i>",
        "HTML",
        {
          reply_markup: {
            force_reply: true,
            input_field_placeholder: "Ej: 482913",
          },
        }
      );
    } else {
      await linkCodeToChat(env, arg, chatId, fromUser);
    }
  } else if (rawCmd === "/start" && arg) {
    await linkCodeToChat(env, arg, chatId, fromUser);
  } else if (rawCmd === "/start") {
    await enqueueCommandForChat(
      env,
      chatId,
      "start",
      "⏳ Inicializando <b>Shakes &amp; Fortune</b>\n\n<i>Si reinstalaste la app o cambiaste de PC, usa /vincular para conectar de nuevo.</i>"
    );
  } else if (rawCmd === "/stop") {
    await enqueueCommandForChat(env, chatId, "stop", "⏳ Enviando <b>/stop</b> a tu PC...");
  } else if (rawCmd === "/status") {
    await enqueueCommandForChat(env, chatId, "status", null);
  } else if (rawCmd === "/desvincular") {
    const client = await env.RELAY_DB.prepare("SELECT secret FROM clients WHERE chat_id = ?")
      .bind(chatId)
      .first();
    if (client) {
      await env.RELAY_DB.batch([
        env.RELAY_DB.prepare("DELETE FROM commands WHERE secret = ?").bind(client.secret),
        env.RELAY_DB.prepare("DELETE FROM clients WHERE chat_id = ?").bind(chatId),
      ]);
      await sendTelegramMessage(env, chatId, "🔌 PC desvinculada. Puedes volver a conectarla cuando quieras.");
    } else {
      await sendTelegramMessage(env, chatId, "ℹ️ No tienes ninguna PC vinculada actualmente.");
    }
  } else if (rawCmd === "/help" || rawCmd === "/ayuda") {
    await sendTelegramMessage(
      env,
      chatId,
      "🍀 <b>Shakes &amp; Fortune — Comandos</b>\n\n" +
        "• /vincular — Vincular tu PC con código de 6 dígitos\n" +
        "• /start — Iniciar el bot en tu PC\n" +
        "• /status — Ver progreso actual\n" +
        "• /stop — Detener el bot\n" +
        "• /desvincular — Desconectar tu PC"
    );
  } else if (!text.startsWith("/")) {
    const digitsOnly = text.replace(/\s+/g, "");
    const awaiting = await env.RELAY_DB.prepare(
      "SELECT expires_at FROM awaiting_pair WHERE chat_id = ?"
    )
      .bind(chatId)
      .first();

    if (/^\d{6}$/.test(digitsOnly)) {
      await linkCodeToChat(env, digitsOnly, chatId, fromUser);
    } else if (awaiting && awaiting.expires_at >= Date.now()) {
      await sendTelegramMessage(
        env,
        chatId,
        "❌ Eso no parece un código de 6 dígitos.\nEnvía solo los 6 números que aparecen en la app (ejemplo: <code>482913</code>)."
      );
    }
  }

  return jsonResponse({ ok: true });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { pathname } = url;
    const method = request.method.toUpperCase();

    if (method === "GET" && pathname === "/health") {
      return jsonResponse({
        ok: true,
        service: "shakes-fortune-relay",
        storage: "d1",
        bot: "@shakes_fortune_bot",
      });
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
