# Shakes & Fortune Bot

Launcher visual estilo menú principal de RPG para automatizar los anuncios del Dr. Abawuwu en Shakes & Fidget, con soporte para **múltiples personajes/servidores**, **bot propio de Telegram** y **cualquier resolución de pantalla**.

## Requisitos

- Windows 10/11
- [Python 3.11+](https://www.python.org/downloads/) — marcar **"Add Python to PATH"** al instalar
- [Google Chrome](https://www.google.com/chrome/)
- Una cuenta de Telegram

---

## Instalación (primera vez — para vos o cualquier amigo)

1. Doble clic en **`Instalar.bat`** (instala las dependencias y Playwright).
2. Doble clic en **`ShakesFortune.bat`** — abre la interfaz principal de **Shakes & Fortune**:
   - **🤖 Configurar Telegram:** creás tu propio bot con [@BotFather](https://t.me/BotFather) (`/newbot`), pegás el token y la app lo valida en vivo.
   - **+ Nuevo Personaje:** agregás nombre y servidor (ej: `EU30`, `EU16`, `US1`) y tocás **Calibrar (1 clic)** sobre la tarjeta de tu personaje en Chrome. Podés guardar todos los personajes que quieras y cambiar entre ellos antes de cada sesión.
   - **🌐 Abrir Chrome (S&F):** abre Chrome en `sfgame.net` con perfil persistente (si ya está abierto en el puerto `9222`, trabaja directo sobre tu pestaña actual sin abrir otra).
   - **▶ INICIAR BOT:** arranca el farmeo al instante (o en espera de `/start` si destildás el auto-inicio) y muestra el registro en vivo y el contador de anuncios en pantalla.

### Comandos de Telegram

| Comando | Descripción |
|---------|-------------|
| `/start` | Inicia el loop infinito de anuncios (y vincula tu cuenta la primera vez) |
| `/stop` | Detiene el bot limpiamente |
| `/status` | Muestra personaje activo, tiempo activo, anuncios vistos y estado actual |

---

## Cómo compartirlo con un amigo

Comprimí la carpeta **SIN** incluir tus archivos personales:
- `config.yaml` (tiene tu token y tu chat_id)
- `state.json`
- `chrome-profile/` (tiene tu sesión de Chrome)

Tu amigo descomprime, corre **`Instalar.bat`** y luego abre **`ShakesFortune.bat`** — todo se configura desde la interfaz visual sin editar archivos de texto.
