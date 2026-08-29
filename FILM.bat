@echo off
REM ============================================================
REM  FILM  --  double-click this. It is the only one.
REM
REM  Three ways to use it, all the same file:
REM
REM    double-click it        carry on with the film you were making
REM    drag files ONTO it     makes a new film out of exactly those
REM                           files and builds it. Nothing to type.
REM    FILM.bat morning01     work on a particular film
REM ============================================================
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 goto :nouv

REM No arguments: carry on where you left off.
if "%~1"=="" (
  uv run film
  goto :done
)

REM An argument that exists on disk is a dropped file or folder.
REM Anything else is the name of a film.
if exist "%~1" (
  uv run film drop %*
) else (
  uv run film next -p "%~1"
)

:done
echo.
pause
exit /b 0

:nouv
echo.
echo ============================================================
echo   Cannot find 'uv', which runs everything here.
echo.
echo   If you have never installed it, open PowerShell and paste
echo   these two lines, one at a time:
echo.
echo     winget install --id astral-sh.uv -e
echo     winget install --id Gyan.FFmpeg -e
echo.
echo   Then close every terminal window and double-click this again.
echo   ^(A window that was already open cannot see a new install.^)
echo ============================================================
echo.
pause
exit /b 1
