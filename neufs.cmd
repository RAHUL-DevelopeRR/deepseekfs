@echo off
setlocal
set "ROOT=%~dp0"
python "%ROOT%neufs.py" %*
