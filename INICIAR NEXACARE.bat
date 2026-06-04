@echo off
cd /d "%~dp0"
title NexaCare — Sistema de Triaje Medico con IA

color 0B
echo.
echo  ==============================================
echo    NexaCare  ^|  Sistema de Triaje Medico
echo    TFG SMR 2025-2026  ^|  Pablo Esteban
echo  ==============================================
echo.
echo  [OK] Credenciales: secrets.toml
echo  [OK] IA: Groq API activa
echo  [OK] Email: Gmail configurado
echo.
echo  Iniciando servidor web...
echo  El navegador se abrira automaticamente.
echo.
echo  Para cerrar la aplicacion cierra esta ventana.
echo  -----------------------------------------------
echo.

start "" http://localhost:8501
py -3.11 -m streamlit run app.py --server.headless true --browser.gatherUsageStats false

echo.
echo  La aplicacion se ha cerrado.
pause
