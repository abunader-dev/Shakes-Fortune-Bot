# 🍀 Shakes & Fortune Bot

Bot visual para automatizar los anuncios de la TV Voladora (Dr. Abawuwu) en **Shakes & Fidget**, controlable desde Telegram con **[@shakes_fortune_bot](https://t.me/shakes_fortune_bot)**.

- Funciona en **cualquier resolución de pantalla** (720p, 1080p, 1440p, 4K, laptops con zoom).
- Soporta **múltiples personajes y servidores** para elegir antes de cada sesión.
- Detecta automáticamente si el juego cierra tu sesión y vuelve a entrar solo.
- Cierra el anuncio **únicamente** después de confirmar `Reward granted` para nunca perder monedas de la suerte.

---

## Requisitos previos (solo la primera vez)

1. **Windows 10 / 11**
2. **Google Chrome** instalado — [Descargar Chrome](https://www.google.com/chrome/)
3. **Python 3.11 o superior** — [Descargar Python](https://www.python.org/downloads/)
   > ⚠️ **MUY IMPORTANTE al instalar Python:** en la primera pantalla del instalador, marca la casilla **"Add python.exe to PATH"** antes de hacer clic en *Install Now*.
4. **Telegram** (en tu celular o computadora)

---

## Instalación paso a paso

### Paso 1 — Descargar el bot
1. Haz clic aquí para descargar el archivo listo para usar:
   👉 **[Descargar ShakesFortune.zip](https://github.com/abunader-dev/Shakes-Fortune-Bot/releases/latest/download/ShakesFortune.zip)**
2. Descomprime `ShakesFortune.zip` — se creará la carpeta **`ShakesFortune`** lista para usar (puedes moverla al Escritorio si prefieres).

### Paso 2 — Instalar dependencias (solo una vez)
1. Entra a la carpeta descomprimida y haz doble clic en **`Instalar.bat`**.
   > 💡 Si Windows muestra una advertencia de *"Editor desconocido"*, es normal porque el archivo viene de GitHub. Solo haz clic en **Ejecutar**.
2. Espera a que termine de instalar los paquetes y el motor de Playwright (tarda ~1 minuto).
3. Cuando aparezca **`Instalacion completada!`**, presiona cualquier tecla para cerrar.

### Paso 3 — Abrir Shakes & Fortune
1. Haz doble clic en **`ShakesFortune.bat`**.
2. Se abrirá el menú principal de **Shakes & Fortune**.

### Paso 4 — Vincular tu cuenta con Telegram (`@shakes_fortune_bot`)
*(Solo se hace una vez — no necesitas crear ningún bot ni editar archivos)*

1. En la ventana de **Shakes & Fortune**, haz clic en el botón **`🍀 Vincular Telegram`**.
2. Aparecerá un **código de 6 dígitos** (ejemplo: `482 913`).
3. Elige cualquiera de estas dos opciones:
   - **Opción rápida (1 clic):** haz clic en el botón verde **`🍀 Abrir @shakes_fortune_bot en Telegram`** y presiona **Iniciar / Start** en Telegram.
   - **Opción manual (desde el celular):** abre Telegram, busca **`@shakes_fortune_bot`** (el del trébol verde 🍀) y envíale:
     ```
     /vincular 482913
     ```
     *(reemplazando `482913` por el código que te muestra la app).*
4. En un par de segundos la app confirmará **`✅ ¡PC vinculada con éxito!`** y la ventana se cerrará sola.

### Paso 5 — Abrir el juego e iniciar sesión
1. En la ventana de **Shakes & Fortune**, haz clic en **`🌐 Abrir Chrome (S&F)`**.
2. Se abrirá Chrome en `https://sfgame.net`.
3. Inicia sesión con tu cuenta de Shakes & Fidget hasta ver la pantalla de **Selección de personaje**.
   > 💡 Esa ventana usa un perfil propio (`chrome-profile`), así que tu sesión queda guardada y no tendrás que volver a iniciar sesión cada día. Si ya la tienes abierta, el bot trabajará sobre esa misma pestaña sin abrir otra.

### Paso 6 — Agregar y calibrar tu personaje (1 clic)
*(Puedes repetir esto para guardar todos los personajes y servidores que quieras)*

1. En **Selección de personaje** dentro de la app (panel izquierdo), haz clic en **`+ Nuevo`**.
2. Escribe el **Nombre** de tu personaje y tu **Servidor** (ejemplo: `EU30`, `EU16`, `US1`, `INT1`).
3. Haz clic en **`🎯 Guardar y calibrar ahora`**.
4. Chrome pasará al frente con un aviso dorado arriba: **haz 1 clic sobre la tarjeta de tu personaje** en la pantalla de selección.
5. ¡Listo! La tarjeta queda guardada como **`✓ Calibrado`** y funcionará en cualquier tamaño de ventana.

### Paso 7 — ¡A farmear!
1. Selecciona el personaje que quieres usar en la lista de la izquierda (queda marcado con ★ dorado).
2. Haz clic en el botón verde **`▶ INICIAR BOT`**.
   - Por defecto empieza a farmear al instante y te envía reportes por **`@shakes_fortune_bot`** cada 5 minutos.
   - Si prefieres iniciarlo solo desde tu celular, desmarca *"Empezar a farmear al instante"* y envía `/start` en Telegram cuando quieras.

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
  Sí. Detén el bot (`■ DETENER BOT`), selecciona otro personaje de tu lista (o crea uno nuevo con `+ Nuevo`) y vuelve a hacer clic en **`▶ INICIAR BOT`**.
* **¿Qué pasa si muevo o cambio el tamaño de la ventana de Chrome?**
  No pasa nada: el bot calcula el área 16:9 real del juego en cada acción.
* **¿Otras personas pueden ver mis datos o mi cuenta?**
  No. Cada usuario vincula su propia PC a su propio chat de Telegram mediante un código privado. Tu sesión de Chrome y tu `config.yaml` solo existen en tu computadora.
* **Dice `Chrome: No abierto` aunque ya tengo mi Chrome normal abierto.**
  Por seguridad de Chrome, el bot solo puede controlar la ventana abierta con el botón **`🌐 Abrir Chrome (S&F)`** (puerto de depuración local `9222`). Usa ese botón una vez y deja esa ventana abierta.
