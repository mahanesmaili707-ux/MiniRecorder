"""MiniRecorder: lightweight mouse and keyboard recorder for Windows."""
from __future__ import annotations
import json, threading, time, tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any
from pynput import keyboard, mouse
from pynput.keyboard import Key, KeyCode

FORMAT_NAME = "MiniRecorder"
FORMAT_VERSION = 1

def validate_recording(data: Any) -> dict:
    if not isinstance(data, dict) or data.get("format") != FORMAT_NAME:
        raise ValueError("Not a MiniRecorder .rec file.")
    if data.get("version") != FORMAT_VERSION:
        raise ValueError(f"Unsupported recording version: {data.get('version')!r}")
    events = data.get("events")
    if not isinstance(events, list):
        raise ValueError("Recording events must be a list.")
    previous = 0.0
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("Each event must be an object with a type.")
        t = event.get("t")
        if not isinstance(t, (int, float)) or isinstance(t, bool) or t < previous:
            raise ValueError("Event times must be non-negative and non-decreasing.")
        previous = float(t)
        if event["type"] not in {"key_down", "key_up", "mouse_move", "mouse_down", "mouse_up", "scroll"}:
            raise ValueError(f"Unknown event type: {event['type']}")
    return data

def key_to_text(key: Any) -> str:
    if isinstance(key, KeyCode):
        if key.char is not None: return "char:" + key.char
        if key.vk is not None: return "vk:" + str(key.vk)
    return "key:" + str(key).removeprefix("Key.")

def text_to_key(value: str) -> Any:
    if value.startswith("char:"): return KeyCode.from_char(value[5:])
    if value.startswith("vk:"): return KeyCode.from_vk(int(value[3:]))
    if value.startswith("key:"):
        name = value[4:]
        if name in Key.__members__: return Key[name]
    raise ValueError(f"Unsupported key value: {value!r}")

class MiniRecorderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("MiniRecorder")
        self.root.geometry("540x350")
        self.root.minsize(500, 320)
        self.state = "Idle"
        self.events = []
        self.record_started = 0.0
        self.play_thread = None
        self.play_stop = threading.Event()
        self.lock = threading.RLock()
        self.held_keys, self.held_buttons = set(), set()
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        self.record_mouse_listener = self.record_keyboard_listener = None
        self.hotkeys = None
        self.status = tk.StringVar(value="Idle")
        self.path = tk.StringVar(value="No file selected")
        self.hotkey_text = tk.StringVar(value="Start: Num 9   Stop: Num 8   Play: Num 7")
        self._build_ui()
        self._start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=16); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="MiniRecorder", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Record and replay mouse + keyboard actions").pack(anchor="w", pady=(0, 12))
        row = ttk.Frame(frame); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Status:", font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(row, textvariable=self.status).pack(side="left", padx=8)
        ttk.Label(frame, textvariable=self.path, wraplength=480).pack(anchor="w", pady=(4, 12))
        buttons = ttk.Frame(frame); buttons.pack(fill="x")
        for label, command in [("Start Recording", self.start_recording), ("Stop Recording", self.stop_recording), ("Play", self.play), ("Stop Playback", self.stop_playback)]:
            ttk.Button(buttons, text=label, command=command).pack(side="left", padx=(0, 6), pady=3)
        files = ttk.Frame(frame); files.pack(fill="x", pady=(8, 4))
        ttk.Button(files, text="Save .rec", command=self.save_file).pack(side="left", padx=(0, 6))
        ttk.Button(files, text="Load .rec", command=self.load_file).pack(side="left")
        ttk.Separator(frame).pack(fill="x", pady=12)
        ttk.Label(frame, textvariable=self.hotkey_text).pack(anchor="w")
        ttk.Label(frame, text="Playback sends real input to the active desktop application.", wraplength=480).pack(anchor="w", pady=(8, 0))

    def _set_state(self, state):
        self.state = state; self.status.set(state)

    def _start_hotkeys(self):
        try:
            self.hotkeys = keyboard.GlobalHotKeys({"<num_9>": self.start_recording, "<num_8>": self.stop_recording, "<num_7>": self.play})
            self.hotkeys.start()
        except Exception as exc:
            self.hotkey_text.set(f"Global hotkeys unavailable: {exc}")

    def start_recording(self):
        with self.lock:
            if self.state in ("Recording", "Playing"): return
            self.events = []; self.record_started = time.perf_counter()
            self._set_state("Recording")
            self.record_keyboard_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
            self.record_mouse_listener = mouse.Listener(on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll)
            self.record_keyboard_listener.start(); self.record_mouse_listener.start()

    def _append(self, event):
        with self.lock:
            if self.state == "Recording":
                event["t"] = round(max(0.0, time.perf_counter() - self.record_started), 6)
                self.events.append(event)

    def _on_key_press(self, key): self._append({"type": "key_down", "key": key_to_text(key)})
    def _on_key_release(self, key): self._append({"type": "key_up", "key": key_to_text(key)})
    def _on_move(self, x, y): self._append({"type": "mouse_move", "x": int(x), "y": int(y)})
    def _on_click(self, x, y, button, pressed):
        self._append({"type": "mouse_down" if pressed else "mouse_up", "x": int(x), "y": int(y), "button": button.name})
    def _on_scroll(self, x, y, dx, dy):
        self._append({"type": "scroll", "x": int(x), "y": int(y), "dx": int(dx), "dy": int(dy)})

    def stop_recording(self):
        with self.lock:
            if self.state != "Recording": return
            self._set_state("Stopped")
            listeners = (self.record_keyboard_listener, self.record_mouse_listener)
            self.record_keyboard_listener = self.record_mouse_listener = None
        for listener in listeners:
            if listener: listener.stop()
        self.root.after(0, lambda: self.path.set(f"Recording captured: {len(self.events)} events (unsaved)"))

    def save_file(self):
        if self.state == "Recording":
            messagebox.showinfo("MiniRecorder", "Stop recording before saving."); return
        filename = filedialog.asksaveasfilename(title="Save recording", defaultextension=".rec", filetypes=[("MiniRecorder recording", "*.rec"), ("JSON files", "*.json")])
        if not filename: return
        with self.lock: data = {"format": FORMAT_NAME, "version": FORMAT_VERSION, "events": list(self.events)}
        try:
            validate_recording(data)
            Path(filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.path.set(filename)
        except Exception as exc: messagebox.showerror("Save failed", str(exc))

    def load_file(self):
        if self.state in ("Recording", "Playing"):
            messagebox.showinfo("MiniRecorder", "Stop the current action before loading."); return
        filename = filedialog.askopenfilename(title="Load recording", filetypes=[("MiniRecorder recording", "*.rec"), ("JSON files", "*.json")])
        if not filename: return
        try:
            data = validate_recording(json.loads(Path(filename).read_text(encoding="utf-8")))
            with self.lock: self.events = data["events"]
            self.path.set(filename); self._set_state("Stopped")
        except Exception as exc: messagebox.showerror("Load failed", str(exc))

    def play(self):
        with self.lock:
            if self.state in ("Recording", "Playing"): return
            if not self.events:
                messagebox.showinfo("MiniRecorder", "Record or load a file first."); return
            try: validate_recording({"format": FORMAT_NAME, "version": FORMAT_VERSION, "events": self.events})
            except Exception as exc:
                messagebox.showerror("Invalid recording", str(exc)); return
            events = list(self.events); self.play_stop.clear(); self._set_state("Playing")
            self.play_thread = threading.Thread(target=self._play_worker, args=(events,), daemon=True); self.play_thread.start()

    def _play_worker(self, events):
        start = time.perf_counter()
        try:
            for event in events:
                if self.play_stop.is_set(): break
                target = start + float(event["t"])
                while not self.play_stop.is_set():
                    remaining = target - time.perf_counter()
                    if remaining <= 0: break
                    self.play_stop.wait(min(remaining, 0.01))
                if self.play_stop.is_set(): break
                self._dispatch(event)
        except Exception as exc:
            self.root.after(0, lambda err=str(exc): messagebox.showerror("Playback failed", err))
        finally:
            self._release_inputs()
            self.root.after(0, lambda: self._set_state("Stopped"))

    def _dispatch(self, event):
        kind = event["type"]
        if kind == "key_down":
            self.keyboard_controller.press(text_to_key(event["key"])); self.held_keys.add(event["key"])
        elif kind == "key_up":
            self.keyboard_controller.release(text_to_key(event["key"])); self.held_keys.discard(event["key"])
        elif kind == "mouse_move": self.mouse_controller.position = (int(event["x"]), int(event["y"]))
        elif kind in ("mouse_down", "mouse_up"):
            button = getattr(mouse.Button, event["button"])
            if kind == "mouse_down": self.mouse_controller.press(button); self.held_buttons.add(event["button"])
            else: self.mouse_controller.release(button); self.held_buttons.discard(event["button"])
        elif kind == "scroll":
            self.mouse_controller.position = (int(event["x"]), int(event["y"]))
            self.mouse_controller.scroll(int(event["dx"]), int(event["dy"]))

    def _release_inputs(self):
        for name in list(self.held_keys):
            try: self.keyboard_controller.release(text_to_key(name))
            except Exception: pass
            self.held_keys.discard(name)
        for name in list(self.held_buttons):
            try: self.mouse_controller.release(getattr(mouse.Button, name))
            except Exception: pass
            self.held_buttons.discard(name)

    def stop_playback(self):
        if self.state == "Playing":
            self.play_stop.set(); self._release_inputs(); self._set_state("Stopped")

    def close(self):
        self.play_stop.set()
        try: self.stop_recording()
        except Exception: pass
        if self.hotkeys: self.hotkeys.stop()
        self._release_inputs(); self.root.destroy()

def main():
    root = tk.Tk(); MiniRecorderApp(root); root.mainloop()

if __name__ == "__main__": main()
