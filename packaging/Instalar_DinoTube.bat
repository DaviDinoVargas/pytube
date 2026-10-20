@echo off
rem Abre o instalador grafico do DinoTube. Pode dar duplo clique neste arquivo.
rem Se o Python nao estiver instalado, oferece instalar (winget) e depois abre a janela do instalador.
setlocal EnableExtensions
cd /d "%~dp0.."
set "PYW="

rem 1) Python ja instalado (com Tk) ?
where py >nul 2>&1 && py -3 -c "import tkinter, sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1 && set "PYW=pyw -3"
if not defined PYW where pythonw >nul 2>&1 && python -c "import tkinter, sys; sys.exit(0 if sys.version_info[:2] >= (3, 10) else 1)" >nul 2>&1 && set "PYW=pythonw"
if defined PYW goto :launch

rem 2) Sem Python utilizavel: pergunta (janela do Windows) e instala pelo winget
where winget >nul 2>&1 || goto :manual
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; $r = [System.Windows.MessageBox]::Show('O DinoTube precisa do Python 3.12 para ser instalado. Posso baixar e instalar o Python agora? (oficial e gratuito)', 'Instalador do DinoTube', 'YesNo', 'Question'); if ($r -eq 'Yes') { exit 0 } else { exit 1 }"
if errorlevel 1 goto :manual
start "Instalando o Python 3.12... aguarde" /wait winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYEXE%" goto :manual
set PYW="%PYEXE%"

:launch
start "" %PYW% "%~dp0installer_gui.pyw"
exit /b 0

:manual
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Instale o Python 3.10 ou mais novo em python.org (mantenha marcado \"tcl/tk and IDLE\" e \"Add python.exe to PATH\") e abra este instalador de novo.', 'Instalador do DinoTube', 'OK', 'Warning') | Out-Null"
exit /b 1
