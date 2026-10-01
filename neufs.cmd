@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%neufs.exe" (
  "%ROOT%neufs.exe" %*
) else if exist "%ROOT%Neuron.exe" (
  "%ROOT%Neuron.exe" --cli %*
) else (
  python "%ROOT%neufs.py" %*
)
