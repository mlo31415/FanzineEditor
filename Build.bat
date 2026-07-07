@echo off
rem Build FanzinesEditor.exe. If FanzinesEditor.ico is present it becomes the exe's icon;
rem if not, the build proceeds with the default icon.
if exist FanzinesEditor.ico (
    .\venv12\Scripts\pyinstaller.exe --onefile --windowed --icon=FanzinesEditor.ico FanzinesEditor.py
) else (
    echo No FanzinesEditor.ico found -- building with the default icon.
    .\venv12\Scripts\pyinstaller.exe --onefile --windowed  FanzinesEditor.py
)
