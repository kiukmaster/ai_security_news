@echo off
chcp 65001 >nul
cd /d "%~dp0"
python main.py %*
if errorlevel 1 (
  echo.
  echo [오류] 실행에 실패했습니다. Python이 설치되어 있는지 확인하세요.
  pause
)
