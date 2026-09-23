@echo off
rem Mieteingang starten: liest den Eingangsordner ein und oeffnet den Browser.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
%PY% -m verwaltung web
pause
