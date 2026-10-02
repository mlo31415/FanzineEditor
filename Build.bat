@echo off
rem Build FanzinesEditor.exe. If FanzinesEditor.ico is present it becomes the exe's icon and is also
rem bundled inside the exe (PyiResourcePath finds it at runtime for the window/taskbar icon).
rem If the icon is absent, the build proceeds with the default icon.
rem The FANAC logo for the page headers stamped on uploaded PDFs is bundled the same way; without it the
rem headers are stamped with no logo.
if exist FanzinesEditor.ico (
    .\venv12\Scripts\pyinstaller.exe --onefile --windowed --icon=FanzinesEditor.ico --add-data "FanzinesEditor.ico;." --add-data "Fanac logo for pdf headers.jpg;." FanzinesEditor.py
) else (
    echo No FanzinesEditor.ico found -- building with the default icon.
    .\venv12\Scripts\pyinstaller.exe --onefile --windowed --add-data "Fanac logo for pdf headers.jpg;." FanzinesEditor.py
)
