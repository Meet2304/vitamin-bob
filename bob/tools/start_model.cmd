@echo off
rem Starts Gemma 4 on llama-server for Bob (http://127.0.0.1:8300). Runs offline.
rem Override locations with VB_LLAMA_DIR / VB_MODEL_DIR; pick the model with VB_MODEL_SIZE=E2B or E4B.
rem E2B is the default: on a 4 GB GPU it transcribes a 25 s clip in ~6 s; E4B takes ~16 s (see README).
setlocal
if "%VB_LLAMA_DIR%"=="" set VB_LLAMA_DIR=%~dp0..\..\..\llama.cpp
if "%VB_MODEL_DIR%"=="" set VB_MODEL_DIR=%~dp0..\..\..\models
if "%VB_MODEL_SIZE%"=="" set VB_MODEL_SIZE=E2B
"%VB_LLAMA_DIR%\llama-server.exe" ^
  -m "%VB_MODEL_DIR%\gemma-4-%VB_MODEL_SIZE%-it-Q8_0.gguf" ^
  --mmproj "%VB_MODEL_DIR%\mmproj-gemma-4-%VB_MODEL_SIZE%-it-BF16.gguf" ^
  --host 127.0.0.1 --port 8300 -c 8192 --jinja
