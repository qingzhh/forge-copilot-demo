@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\build_portable_exe.py
endlocal
