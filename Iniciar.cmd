@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.11 -m venv .venv
  if errorlevel 1 goto failed
)
if not exist .venv\installed.ok (
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
  echo installed>.venv\installed.ok
)
.venv\Scripts\python.exe start.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Falha ao iniciar. Confira Python 3.11, FFmpeg e as dependencias no README.
pause
exit /b 1
