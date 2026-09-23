@echo off
rem Demo mit erfundenen Daten (Max Mustermann und Co.) erzeugen und oeffnen.
cd /d "%~dp0"
set PY=python
where py >nul 2>nul && set PY=py
%PY% -m verwaltung demo
if errorlevel 1 goto ende
%PY% -m verwaltung --demo web
:ende
pause
