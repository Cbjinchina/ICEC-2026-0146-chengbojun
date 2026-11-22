@echo off
cd /d "%~dp0"
echo ==== blind test demo (15 held-out segments) ====
echo.
"C:\Users\chengbojun\.workbuddy\binaries\python\versions\3.13.12\python.exe" src\demo_blind.py --features features.csv --each 3 --slow
echo.
echo ==== done, press any key to close ====
pause >nul
