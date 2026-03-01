@echo off
REM Build VideoDeathCutter.exe for Windows
REM Requires ffmpeg.exe and ffprobe.exe in the same directory or on PATH

where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: ffmpeg not found. Install via: winget install ffmpeg
    exit /b 1
)

for /f "tokens=*" %%i in ('where ffmpeg') do set FFMPEG_PATH=%%i
for /f "tokens=*" %%i in ('where ffprobe') do set FFPROBE_PATH=%%i

echo Using ffmpeg: %FFMPEG_PATH%
echo Using ffprobe: %FFPROBE_PATH%

pyinstaller ^
    --windowed ^
    --name "VideoDeathCutter" ^
    --add-binary "%FFMPEG_PATH%;." ^
    --add-binary "%FFPROBE_PATH%;." ^
    --hidden-import "PyQt6.QtMultimedia" ^
    --hidden-import "PyQt6.QtMultimediaWidgets" ^
    --hidden-import "editor" ^
    --collect-all PyQt6 ^
    main.py

echo.
echo Build complete: dist\VideoDeathCutter.exe
