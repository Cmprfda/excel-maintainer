@echo off
setlocal

echo A instalar o Excel Maintainer...
echo.

set "PY="
python --version >nul 2>&1
if not errorlevel 1 set "PY=python"

if not defined PY (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
)

if not defined PY (
    echo.
    echo ERRO: o Python nao esta instalado neste computador.
    echo.
    echo Instale o Python a partir de https://www.python.org/downloads/
    echo Durante a instalacao, marque a opcao "Add Python to PATH"
    echo ^(adicionar ao PATH^) e depois volte a correr este ficheiro.
    echo.
    pause
    exit /b 1
)

echo A atualizar o instalador de pacotes...
%PY% -m pip install --upgrade pip >nul 2>&1

echo A instalar os componentes necessarios...
%PY% -m pip install pywebview
if errorlevel 1 (
    echo.
    echo ERRO: nao foi possivel instalar os componentes necessarios.
    echo Verifique a ligacao a internet e volte a correr este ficheiro.
    echo.
    pause
    exit /b 1
)

%PY% -c "import webview" 2>nul
if errorlevel 1 (
    echo.
    echo ERRO: a instalacao dos componentes nao ficou completa.
    echo Verifique a ligacao a internet e volte a correr este ficheiro.
    echo.
    pause
    exit /b 1
)

echo A criar o icone no ambiente de trabalho...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
if errorlevel 1 (
    echo.
    echo AVISO: nao foi possivel criar o icone no ambiente de trabalho.
    echo A aplicacao ficou instalada na mesma: pode abri-la com o ficheiro run.bat
    echo que esta nesta pasta.
)

echo.
echo Instalacao concluida. Pode abrir a aplicacao atraves do icone
echo "Excel Maintainer" no ambiente de trabalho.
echo.
pause
