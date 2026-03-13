#!/usr/bin/env python3
"""
PyGem - Automated Gemini Image-to-Manim Code Generator

A tkinter GUI application that automates sending images to the Gemini Web App,
extracting the generated Manim code, and rendering it automatically.
"""

import io
import os
import platform
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import webbrowser

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    from PIL import Image
except ImportError:
    Image = None

SYSTEM = platform.system()

DEFAULT_URL = "https://gemini.google.com/app"
DEFAULT_WAIT = 30
DEFAULT_PROMPT = (
    "Solve the problem in this image using the Manim library with animations. "
    "Output ONLY the runnable Python code block. "
    "Do not write any other explanations."
)


# ---------------------------------------------------------------------------
# Cross-platform clipboard helpers
# ---------------------------------------------------------------------------

def copy_image_to_clipboard(image_path: str) -> None:
    """Copy an image file to the system clipboard.

    Supports Windows (via win32clipboard) and macOS (via osascript).
    On Linux, falls back to xclip if available.
    """
    abs_path = os.path.abspath(image_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Image not found: {abs_path}")

    if SYSTEM == "Windows":
        _copy_image_windows(abs_path)
    elif SYSTEM == "Darwin":
        _copy_image_mac(abs_path)
    else:
        _copy_image_linux(abs_path)


def _copy_image_windows(image_path: str) -> None:
    """Copy image to clipboard on Windows using win32clipboard."""
    import win32clipboard  # type: ignore[import-untyped]

    if Image is None:
        raise ImportError("Pillow is required: pip install Pillow")

    img = Image.open(image_path)
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    bmp_data = output.getvalue()[14:]  # strip BMP file header
    output.close()

    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
    finally:
        win32clipboard.CloseClipboard()


def _copy_image_mac(image_path: str) -> None:
    """Copy image to clipboard on macOS using osascript."""
    script = (
        'set the clipboard to '
        f'(read (POSIX file "{image_path}") as «class PNGf»)'
    )
    subprocess.run(["osascript", "-e", script], check=True)


def _copy_image_linux(image_path: str) -> None:
    """Copy image to clipboard on Linux using xclip."""
    mime = "image/png"
    if image_path.lower().endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    subprocess.run(
        ["xclip", "-selection", "clipboard", "-t", mime, "-i", image_path],
        check=True,
    )


# ---------------------------------------------------------------------------
# Manim code extraction helper
# ---------------------------------------------------------------------------

def extract_manim_code(text: str) -> str | None:
    """Return the first Python/Manim fenced code block found in *text*."""
    pattern = r"```(?:python)?\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Modifier key helper
# ---------------------------------------------------------------------------

def _mod_key() -> str:
    """Return the platform modifier key name used by pyautogui."""
    return "command" if SYSTEM == "Darwin" else "ctrl"


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

class PyGemApp:
    """Tkinter GUI for the Gemini automation workflow."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PyGem – Gemini Image-to-Manim Automation")
        self.root.resizable(True, True)

        self.image_paths: list[str] = []
        self._running = False

        self._build_ui()

    # ---- UI construction --------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 6, "pady": 3}

        # --- URL ---
        frm_url = tk.Frame(self.root)
        frm_url.pack(fill=tk.X, **pad)
        tk.Label(frm_url, text="Gemini URL:").pack(side=tk.LEFT)
        self.url_var = tk.StringVar(value=DEFAULT_URL)
        tk.Entry(frm_url, textvariable=self.url_var, width=50).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0)
        )

        # --- Wait time ---
        frm_wait = tk.Frame(self.root)
        frm_wait.pack(fill=tk.X, **pad)
        tk.Label(frm_wait, text="Wait Time (s):").pack(side=tk.LEFT)
        self.wait_var = tk.IntVar(value=DEFAULT_WAIT)
        tk.Entry(frm_wait, textvariable=self.wait_var, width=6).pack(
            side=tk.LEFT, padx=(4, 0)
        )

        # --- Prompt ---
        tk.Label(self.root, text="Prompt:").pack(anchor=tk.W, **pad)
        self.prompt_text = scrolledtext.ScrolledText(
            self.root, height=5, wrap=tk.WORD
        )
        self.prompt_text.pack(fill=tk.X, **pad)
        self.prompt_text.insert(tk.END, DEFAULT_PROMPT)

        # --- Image queue ---
        frm_img = tk.LabelFrame(self.root, text="Image Queue")
        frm_img.pack(fill=tk.BOTH, expand=True, **pad)

        self.img_listbox = tk.Listbox(frm_img, selectmode=tk.EXTENDED)
        self.img_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=4, pady=4)

        frm_btns = tk.Frame(frm_img)
        frm_btns.pack(side=tk.RIGHT, padx=4, pady=4)
        tk.Button(frm_btns, text="Add Photos", command=self._add_photos).pack(
            fill=tk.X, pady=2
        )
        tk.Button(frm_btns, text="Clear List", command=self._clear_list).pack(
            fill=tk.X, pady=2
        )

        # --- Log console ---
        tk.Label(self.root, text="Log Console:").pack(anchor=tk.W, **pad)
        self.log_console = scrolledtext.ScrolledText(
            self.root, height=10, state=tk.DISABLED, wrap=tk.WORD
        )
        self.log_console.pack(fill=tk.BOTH, expand=True, **pad)

        # --- Start button ---
        self.start_btn = tk.Button(
            self.root, text="Start", command=self._on_start, bg="#4CAF50", fg="white"
        )
        self.start_btn.pack(fill=tk.X, **pad)

    # ---- Image list management --------------------------------------------

    def _add_photos(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Images",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("All files", "*.*"),
            ],
        )
        for p in paths:
            self.image_paths.append(p)
            self.img_listbox.insert(tk.END, os.path.basename(p))

    def _clear_list(self) -> None:
        self.image_paths.clear()
        self.img_listbox.delete(0, tk.END)

    # ---- Logging ----------------------------------------------------------

    def _log(self, message: str) -> None:
        """Append a message to the log console (thread-safe)."""
        def _append() -> None:
            self.log_console.config(state=tk.NORMAL)
            self.log_console.insert(tk.END, message + "\n")
            self.log_console.see(tk.END)
            self.log_console.config(state=tk.DISABLED)

        self.root.after(0, _append)

    # ---- Automation -------------------------------------------------------

    def _on_start(self) -> None:
        if self._running:
            self._log("[WARN] Automation is already running.")
            return

        # Pre-flight checks
        missing: list[str] = []
        if pyautogui is None:
            missing.append("pyautogui")
        if pyperclip is None:
            missing.append("pyperclip")
        if Image is None:
            missing.append("Pillow")
        if missing:
            messagebox.showerror(
                "Missing dependencies",
                "Please install: " + ", ".join(missing),
            )
            return

        if not self.image_paths:
            messagebox.showwarning("No images", "Please add at least one image.")
            return

        self._running = True
        self.start_btn.config(state=tk.DISABLED)
        thread = threading.Thread(target=self._run_automation, daemon=True)
        thread.start()

    def _run_automation(self) -> None:
        """Main automation loop executed in a background thread."""
        try:
            url = self.url_var.get().strip() or DEFAULT_URL
            wait_time = self.wait_var.get()
            prompt = self.prompt_text.get("1.0", tk.END).strip()
            mod = _mod_key()

            self._log(f"[INFO] Opening {url} in default browser …")
            webbrowser.open(url)
            self._log("[INFO] Waiting 10 s for page to load …")
            time.sleep(10)

            for idx, img_path in enumerate(self.image_paths, start=1):
                self._log(
                    f"\n[{idx}/{len(self.image_paths)}] Processing: "
                    f"{os.path.basename(img_path)}"
                )

                # 1. Copy image to clipboard and paste
                self._log("[INFO] Copying image to clipboard …")
                try:
                    copy_image_to_clipboard(img_path)
                except Exception as exc:
                    self._log(f"[ERROR] Failed to copy image: {exc}")
                    continue

                self._log("[INFO] Pasting image into chat …")
                pyautogui.hotkey(mod, "v")
                time.sleep(2)

                # 2. Copy prompt and paste
                self._log("[INFO] Pasting prompt …")
                pyperclip.copy(prompt)
                pyautogui.hotkey(mod, "v")
                time.sleep(1)

                # 3. Press Enter to send
                self._log("[INFO] Sending message …")
                pyautogui.press("enter")

                # 4. Wait for Gemini response
                self._log(f"[INFO] Waiting {wait_time} s for Gemini response …")
                time.sleep(wait_time)

                # 5. Select all, copy page content, deselect
                self._log("[INFO] Copying page content …")
                pyautogui.hotkey(mod, "a")
                time.sleep(0.5)
                pyautogui.hotkey(mod, "c")
                time.sleep(0.5)
                pyautogui.press("right")  # deselect
                time.sleep(0.5)

                page_content = pyperclip.paste()

                # 6. Extract Manim code
                code = extract_manim_code(page_content)
                if code is None:
                    self._log(
                        "[WARN] No Python code block found in the response. "
                        "Skipping render."
                    )
                    continue

                # 7. Save and render
                out_dir = os.path.join(os.getcwd(), "manim_output")
                os.makedirs(out_dir, exist_ok=True)
                script_name = f"scene_{idx}.py"
                script_path = os.path.join(out_dir, script_name)

                with open(script_path, "w", encoding="utf-8") as fh:
                    fh.write(code + "\n")
                self._log(f"[INFO] Saved Manim script → {script_path}")

                self._log("[INFO] Rendering with Manim …")
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "manim", "render", script_path],
                        capture_output=True,
                        text=True,
                    )
                    if result.returncode == 0:
                        self._log("[INFO] Manim render succeeded ✓")
                    else:
                        self._log(f"[ERROR] Manim render failed:\n{result.stderr}")
                except FileNotFoundError:
                    self._log(
                        "[ERROR] Manim is not installed. "
                        "Install it with: pip install manim"
                    )

            self._log("\n[INFO] All images processed. Done!")

        except Exception as exc:
            self._log(f"[ERROR] Unexpected error: {exc}")
        finally:
            self._running = False
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    root = tk.Tk()
    PyGemApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
