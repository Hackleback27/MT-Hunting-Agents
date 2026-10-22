@echo off
rem One-time setup: names your commits, saves the first version, and uploads it to GitHub.
cd /d "%~dp0"

git config user.name "Hackleback27"
git config user.email "Hackleback27@users.noreply.github.com"

git add -A
git commit -m "First version: FWP deer data, website, Excel export"

git branch -M main
git remote remove origin 2>nul
git remote add origin https://github.com/Hackleback27/MT-Hunting-Agents.git
git push -u origin main

echo.
if %errorlevel%==0 (echo Uploaded! You can delete first_upload.bat now.) else (echo Something went wrong - copy the message above and send it to Claude.)
pause
