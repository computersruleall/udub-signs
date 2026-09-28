@echo off
title Wayfinder
cd /d "%~dp0"
py -3 serve.py
if errorlevel 9009 python serve.py
pause
