@echo off
chcp 65001 >nul
title DeliveryBot - Painel Principal
cd /d "%~dp0"
if exist "%~dp0dist\DeliveryBot.exe" (
    start "" "%~dp0dist\DeliveryBot.exe"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "iniciar.ps1"
echo.
echo Esta janela pode ficar aberta ou ser fechada -- o sistema continua
echo rodando nas outras duas janelas (ngrok e Sistema).
echo.
pause
