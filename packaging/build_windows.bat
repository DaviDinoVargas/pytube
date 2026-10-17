@echo off
rem Gera dist\DinoTube\DinoTube.exe. Rode na raiz do projeto: packaging\build_windows.bat
setlocal
cd /d "%~dp0\.."

python -m pip install -r requirements.txt pyinstaller || exit /b 1
python packaging\make_icon.py || exit /b 1
python -m PyInstaller DinoTube.spec --noconfirm --clean || exit /b 1

echo.
echo Pronto: dist\DinoTube\DinoTube.exe
endlocal
