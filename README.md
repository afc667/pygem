# PyGem – Gemini Image-to-Manim Automation

A single-file tkinter GUI application that automates sending images to the
[Gemini Web App](https://gemini.google.com/app), extracting the generated
[Manim](https://www.manim.community/) code, and rendering it automatically.

## Features

- **Gemini URL input** – defaults to `https://gemini.google.com/app`.
- **Wait time** – configurable delay (default 30 s) to wait for Gemini's
  response.
- **Prompt editor** – pre-filled with a Manim-specific prompt; fully editable.
- **Image queue** – add multiple images via a file dialog; clear at any time.
- **Log console** – real-time progress, info, and error messages.
- **Start button** – kicks off the automation in a background thread so the
  GUI stays responsive.
- **Cross-platform clipboard** – supports Windows (`win32clipboard`), macOS
  (`osascript`), and Linux (`xclip`).
- **Automatic Manim rendering** – extracted code is saved and rendered via
  `manim render`.

## Requirements

- Python 3.10+
- tkinter (included with most Python installations)

Install runtime dependencies:

```bash
pip install -r requirements.txt
```

### Platform-specific notes

| Platform | Extra requirement |
|----------|-------------------|
| Windows  | `pip install pywin32` (for `win32clipboard`) |
| macOS    | None (`osascript` is built-in) |
| Linux    | `sudo apt install xclip` |

To render Manim scenes you also need Manim installed:

```bash
pip install manim
```

## Usage

```bash
python pygem.py
```

1. (Optional) Edit the Gemini URL and wait time.
2. Click **Add Photos** to queue one or more images.
3. Adjust the prompt if needed.
4. Click **Start**.
5. The script opens Gemini in your default browser, pastes each image with the
   prompt, waits for the response, extracts any Python code block, and renders
   it with Manim. Results are saved under `manim_output/`.