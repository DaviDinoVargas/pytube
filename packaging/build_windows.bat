@echo off
rem Gera dist\DinoTube\DinoTube.exe. Pode dar duplo clique ou rodar: packaging\build_windows.bat
rem Usa um ambiente virtual proprio (.venv-build): evita conflito com outros pacotes Qt instalados no seu Python.
setlocal EnableExtensions
cd /d "%~dp0.."
set "LOG=%CD%\packaging\build.log"
set "VPY=%CD%\.venv-build\Scripts\python.exe"

echo ================================================
echo  Gerando o DinoTube (isso leva alguns minutos)
echo  Registro completo: packaging\build.log
echo ================================================
> "%LOG%" echo Build iniciado em %date% %time%

echo [1/6] Procurando o Python...
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto :nopython
%PY% --version
%PY% -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" || goto :oldpython

echo [2/6] Conferindo o ffmpeg que acompanha o programa...
if not exist "third_party\ffmpeg\bin\ffmpeg.exe" goto :noffmpeg
if not exist "third_party\ffmpeg\bin\ffprobe.exe" goto :noffmpeg

echo [3/6] Preparando o ambiente de build (.venv-build)...
if not exist "%VPY%" %PY% -m venv .venv-build >> "%LOG%" 2>&1
if not exist "%VPY%" goto :novenv

echo [4/6] Instalando as dependencias (a primeira vez baixa varios arquivos)...
"%VPY%" -m pip install --upgrade pip >> "%LOG%" 2>&1
"%VPY%" -m pip install -r requirements.txt pyinstaller >> "%LOG%" 2>&1 || goto :fail

echo [5/6] Gerando o icone...
"%VPY%" packaging\make_icon.py >> "%LOG%" 2>&1 || goto :fail

echo [6/6] Empacotando com o PyInstaller...
taskkill /f /im DinoTube.exe >nul 2>&1
"%VPY%" -m PyInstaller DinoTube.spec --noconfirm --clean >> "%LOG%" 2>&1 || goto :fail
if not exist "dist\DinoTube\DinoTube.exe" goto :fail

echo.
echo ================================================
echo  PRONTO: dist\DinoTube\DinoTube.exe
echo  Distribua a pasta dist\DinoTube inteira.
echo ================================================
pause
exit /b 0

:nopython
echo.
echo ERRO: o Python nao foi encontrado. Instale o Python 3.10 ou mais novo em python.org
echo       e marque "Add python.exe to PATH" na instalacao. Depois rode este arquivo de novo.
goto :end

:oldpython
echo.
echo ERRO: o Python e muito antigo. Instale o Python 3.10 ou mais novo.
goto :end

:noffmpeg
echo.
echo ERRO: faltam third_party\ffmpeg\bin\ffmpeg.exe e ffprobe.exe. Baixe o projeto completo
echo       (git clone ou o ZIP inteiro do GitHub) e rode de novo.
goto :end

:novenv
echo.
echo ERRO: nao consegui criar o ambiente virtual. Detalhes em packaging\build.log
goto :showlog

:fail
echo.
echo ERRO: o build falhou. Ultimas linhas do registro:
:showlog
echo ------------------------------------------------
powershell -NoProfile -Command "Get-Content -Tail 30 -LiteralPath '%LOG%'"
echo ------------------------------------------------
echo Registro completo em: %LOG%

:end
echo.
pause
exit /b 1
