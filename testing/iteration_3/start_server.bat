@echo off
echo ========================================
echo Starting Doctor Follow API Server
echo ========================================
echo.

REM Activate virtual environment
echo [1/2] Activating virtual environment...
call ..\venvsdoctorfollow\Scripts\activate.bat

REM Start the FastAPI server
echo [2/2] Starting FastAPI server...
echo.
echo Server will be available at:
echo   - API: http://localhost:8000
echo   - Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

python api_server.py
