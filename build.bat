@echo off
title Compilando HDD Terminator Ultimate a EXE...
cd /d "%~dp0"
echo =======================================================
echo   COMPILANDO HDD TERMINATOR ULTIMATE A EJECUTABLE (.EXE)
echo =======================================================
echo.

pyinstaller --noconfirm --onedir --windowed --uac-admin --name "HDD_Terminator_Ultimate" --collect-all customtkinter --collect-all serial --add-data "core;core" --add-data "ui;ui" main.py

echo.
if exist "dist\HDD_Terminator_Ultimate\HDD_Terminator_Ultimate.exe" (
    echo =======================================================
    echo   EXITO: Ejecutable generado en:
    echo   dist\HDD_Terminator_Ultimate\HDD_Terminator_Ultimate.exe
    echo =======================================================
) else (
    echo [ERROR] No se pudo generar el ejecutable.
)
pause
