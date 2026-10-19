# MiniRecorder

A lightweight desktop utility for recording and replaying mouse and keyboard input.

## Features
- Tkinter GUI with Idle, Recording, Playing and Stopped states.
- Keyboard key-down/key-up events, mouse movement, button clicks and wheel scrolling.
- Timestamp-based playback preserves delays between events, including key holds.
- Save/load JSON-based .rec recordings.
- Global hotkeys: NumPad 9 starts recording, NumPad 8 stops recording, NumPad 7 starts playback.
- Windows executable build via GitHub Actions.

## Run from source
Requires Python 3.10 or newer. On Windows, install Python with Tcl/Tk support.

    py -m pip install -r requirements.txt
    py minirecorder.py

The app may need the same privilege level as the target application. Do not run as administrator unless necessary.

## Build the Windows executable
Open the repository Actions tab and run the Build Windows EXE workflow, or push a commit to main. Download the MiniRecorder-Windows artifact from a successful run. The artifact contains MiniRecorder.exe.

## Recording format
.rec files are UTF-8 JSON with format, version, and an ordered events list. Times are seconds from the start of recording. This format is intended for MiniRecorder; compatibility with MTA's native recording formats is not claimed.

## Notes and limitations
- Playback moves the real pointer and sends real key/button events to the active desktop. Test in a safe, non-destructive application first.
- Absolute screen coordinates are recorded; changing screen resolution or display layout may affect playback.
- Some games, elevated apps, anti-cheat systems, Raw Input, or exclusive/full-screen input paths may ignore simulated input. Compatibility with MTA is not guaranteed.
- Hotkey behavior can vary with keyboard layout and Num Lock state.
- Use only where automation is permitted. The app does not bypass anti-cheat or access controls.

## Tests
    py -m unittest discover -s tests -v
