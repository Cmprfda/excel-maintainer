@echo off
if "%1"=="" (
    echo Usage: make_release.bat v1.2.3
    exit /b 1
)
set TAG=%1
git add -A
git commit -m "Release %TAG%" 2>nul || echo (nothing new to commit)
git tag %TAG%
git push origin master
git push origin %TAG%
echo.
echo Released %TAG% successfully.
