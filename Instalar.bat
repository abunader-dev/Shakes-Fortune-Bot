@echo off
title Shakes & Fortune - Instalacion
color 0B
cd /d "%~dp0"

echo ============================================
echo     Shakes ^& Fortune - Instalacion
echo ============================================
echo.

:: Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado.
    echo Descargalo de https://www.python.org/downloads/
    echo Asegurate de marcar "Add python.exe to PATH" al instalar.
    pause
    exit /b 1
)

echo [OK] Python encontrado.
echo.

:: Instalar dependencias
echo [1/2] Instalando paquetes necesarios...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion de paquetes.
    pause
    exit /b 1
)

echo.
echo [2/2] Instalando motor del navegador...
python -m playwright install chromium
if errorlevel 1 (
    echo [ERROR] Fallo la instalacion del navegador.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Instalacion completada!
echo.
echo  SIGUIENTE PASO:
echo  Haz doble clic en "ShakesFortune.bat"
echo  para abrir el launcher, vincular Telegram
echo  y elegir tu personaje.
echo ============================================
echo.
pause
