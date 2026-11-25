# 🍀 Shakes & Fortune Bot

Bot visual para automatizar los anuncios de la TV Voladora (Dr. Abawuwu) en **Shakes & Fidget**, controlable desde Telegram con **[@shakes_fortune_bot](https://t.me/shakes_fortune_bot)**.

- Funciona en **cualquier resolución de pantalla** (720p, 1080p, 1440p, 4K, notebooks con zoom).
- Soporta **múltiples personajes y servidores** para elegir antes de cada sesión.
- Detecta automáticamente si el juego te desloguea y vuelve a entrar solo.
- Cierra el anuncio **únicamente** después de confirmar `Reward granted` para nunca perder monedas de la suerte.

---

## Requisitos previos (solo la primera vez)

1. **Windows 10 / 11**
2. **Google Chrome** instalado — [Descargar Chrome](https://www.google.com/chrome/)
3. **Python 3.11 o superior** — [Descargar Python](https://www.python.org/downloads/)
   > ⚠️ **MUY IMPORTANTE al instalar Python:** en la primera pantalla del instalador, marcá la casilla **"Add python.exe to PATH"** antes de tocar *Install Now*.
4. **Telegram** (en tu celular o PC)

---

## Instalación paso a paso

### Paso 1 — Descargar el bot
1. En esta página de GitHub, tocá el botón verde **`<> Code`** → **`Download ZIP`**.
2. Descomprimí el archivo `.zip` en una carpeta de tu PC (por ejemplo en el Escritorio).

### Paso 2 — Instalar dependencias (solo una vez)
1. Entrá a la carpeta descomprimida y dale doble clic a **`Instalar.bat`**.
2. Esperá a que termine de instalar los paquetes y el motor de Playwright (tarda ~1 minuto).
3. Cuando diga **`Instalacion completada!`**, presioná cualquier tecla para cerrar.

### Paso 3 — Abrir Shakes & Fortune
1. Dale doble clic a **`ShakesFortune.bat`**.
2. Se abrirá el menú principal de **Shakes & Fortune**.

### Paso 4 — Vincular tu cuenta con Telegram (`@shakes_fortune_bot`)
*(Solo se hace una vez — no necesitás crear ningún bot ni editar archivos)*

1. En la ventana de **Shakes & Fortune**, tocá el botón **`🍀 Vincular Telegram`**.
2. Va a aparecer un **código de 6 dígitos** (ejemplo: `482 913`).
3. Elegí cualquiera de estas dos formas:
   - **Forma rápida (1 clic):** tocá el botón verde **`🍀 Abrir @shakes_fortune_bot en Telegram`** y presioná **Iniciar / Start** en Telegram.
   - **Forma manual (desde el celular):** abrí Telegram, buscá **`@shakes_fortune_bot`** (el del trébol verde 🍀) y mandale:
     ```
     /vincular 482913
     ```
     *(reemplazando `482913` por el código que te muestra la app).*
4. En 2 segundos la app confirma **`✅ ¡PC vinculada con éxito!`** y se cierra sola.

### Paso 5 — Abrir el juego e iniciar sesión
1. En la ventana de **Shakes & Fortune**, tocá **`🌐 Abrir Chrome (S&F)`**.
2. Se abrirá Chrome en `https://sfgame.net`.
3. Iniciá sesión con tu cuenta de Shakes & Fidget hasta ver la pantalla de **Selección de personaje**.
   > 💡 Esa ventana usa un perfil propio (`chrome-profile`), así que tu sesión queda recordada y no vas a tener que volver a loguearte cada día. Si ya la dejás abierta, el bot siempre trabaja sobre esa misma pestaña sin abrir otra.

### Paso 6 — Agregar y calibrar tu personaje (1 clic)
*(Podés repetir esto para guardar todos los personajes y servidores que quieras)*

1. En **Selección de personaje** dentro de la app (panel izquierdo), tocá **`+ Nuevo`**.
2. Escribí el **Nombre** de tu personaje y tu **Servidor** (ejemplo: `EU30`, `EU16`, `US1`, `INT1`).
3. Tocá **`🎯 Guardar y calibrar ahora`**.
4. Chrome pasará al frente con un cartel dorado arriba: **hacé 1 clic sobre la tarjeta de tu personaje** en la pantalla de selección.
5. ¡Listo! La tarjeta queda guardada como **`✓ Calibrado`** y funcionará en cualquier tamaño de ventana.

### Paso 7 — ¡A farmear!
1. Seleccioná el personaje que querés usar en la lista de la izquierda (queda marcado con ★ dorado).
2. Tocá el botón verde **`▶ INICIAR BOT`**.
   - Por defecto empieza a farmear al instante y te avisa por **`@shakes_fortune_bot`** cada 5 minutos.
   - Si preferís arrancarlo solo desde tu celular, destildá *"Empezar a farmear al instante"* y mandá `/start` en Telegram cuando quieras.

---

## Comandos en Telegram (`@shakes_fortune_bot`)

| Comando | Qué hace |
|---------|----------|
| `/start` | Inicia el farmeo infinito de anuncios en tu PC |
| `/status` | Muestra personaje activo, tiempo corriendo, anuncios vistos y estado actual |
| `/stop` | Detiene el bot limpiamente |
| `/vincular CODIGO` | Vincula una PC nueva con el código de 6 dígitos |
| `/desvincular` | Desconecta tu PC actual de Telegram |
| `/ayuda` | Muestra la lista de comandos |

---

## Preguntas frecuentes

* **¿Puedo cambiar de personaje o servidor?**
  Sí. Detené el bot (`■ DETENER BOT`), tocá otro personaje de tu lista (o creá uno nuevo con `+ Nuevo`) y volvé a tocar **`▶ INICIAR BOT`**.
* **¿Qué pasa si muevo o cambio el tamaño de la ventana de Chrome?**
  No pasa nada: el bot calcula el área 16:9 real del juego en cada acción.
* **¿Mis amigos ven mis datos o mi cuenta?**
  No. Cada usuario vincula su propia PC a su propio chat de Telegram mediante un código privado. Tu sesión de Chrome y tu `config.yaml` solo existen en tu computadora.
* **Dice `Chrome: No abierto` aunque ya tengo mi Chrome normal abierto.**
  Por seguridad de Chrome, el bot solo puede controlar la ventana abierta con el botón **`🌐 Abrir Chrome (S&F)`** (puerto de depuración local `9222`). Usá ese botón una vez y dejá esa ventana abierta.
