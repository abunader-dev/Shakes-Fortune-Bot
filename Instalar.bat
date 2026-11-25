@echo off
title S^&F Bot - Instalacion
color 0B
cd /d "%~dp0"

echo ============================================
echo     S^&F Bot - Instalacion de dependencias
echo ============================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo Descargalo de https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" al instalar.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

:: Instalar dependencias
echo [1/2] Instalando paquetes Python...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de paquetes.
    pause
    exit /b 1
)

echo.
echo [2/2] Instalando navegador Playwright (Chromium)...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de Playwright.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Instalacion completada!
echo.
echo  SIGUIENTE PASO:
echo  1. Copia config.example.yaml a config.yaml
echo  2. Edita config.yaml con tu token de Telegram
echo     y tu chat_id (ver instrucciones adentro)
echo  3. Ejecuta "Iniciar Bot.bat" para arrancar
echo ============================================
echo.
pause

