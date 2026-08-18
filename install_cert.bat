@echo off
:: Comprobar y solicitar permisos de Administrador
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [INFO] Solicitando permisos de Administrador para instalar el certificado...
    powershell -Command "Start-Process '%~0' -Verb RunAs"
    exit /b
)

title Instalador de Certificado - HDD Terminator Ultimate
cd /d "%~dp0"
echo ========================================================
echo   INSTALACION DE CERTIFICADO DE CONFIANZA (AUTHENTICODE)
echo ========================================================
echo.
if not exist "HDD_Terminator_Certificate.cer" (
    echo [ERROR] No se encuentra el archivo HDD_Terminator_Certificate.cer
    pause
    exit /b 1
)

echo Instalando certificado en Entidades de Certificacion Raiz de Confianza...
certutil -addstore -f "Root" "HDD_Terminator_Certificate.cer"

echo Instalando certificado en Editores de Confianza...
certutil -addstore -f "TrustedPublisher" "HDD_Terminator_Certificate.cer"

echo.
echo ========================================================
echo   [EXITO] Certificado instalado correctamente.
echo   La aplicacion se ejecutara sin advertencias de SmartScreen.
echo ========================================================
echo.
pause
