# Laixot

Laixot is a lightweight, background Windows screenshot application designed for quickly capturing areas on your screen, marking them with an anti-aliased arrow, adding a watermark, and saving them as highly compressed, web-optimized `.webp` files.

## Features

- **Background Listener**: Runs silently in the background. Press a hotkey from anywhere to start a capture.
- **Smart Multi-Monitor Support**: Detects the monitor your cursor is on and captures only that monitor.
- **On-Screen Snipping**: Crosshair cursor with a real-time selection rectangle natively built on `tkinter`.
- **Anti-Aliased Arrow Drawing**: Click and drag to point out elements in the screenshot. The arrow is drawn using 4x supersampling + Lanczos downscaling for perfect anti-aliasing without needing external vector libraries.
- **Web-Optimized Size**: Saves directly to `.webp` format with `quality=75` and max encoding effort, producing incredibly small files with exceptional visual quality compared to PNG.
- **Dynamic Watermark**: Automatically overlays `watermark.png` in the bottom right corner of the capture. The watermark scales automatically based on the captured image's width (max 80px).
- **Auto-Increment Naming**: Automatically saves files to a `captures/` folder as `laixot_1.webp`, `laixot_2.webp`, etc., intelligently picking the next available number without relying on timestamps.

## Prerequisites

- Python 3.9+
- Windows (utilizes `ctypes.wintypes` and `ctypes.windll.shcore.SetProcessDpiAwareness` for DPI scaling correction).

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/PCSolucion/laixot.git
   cd laixot
   ```

2. Install the required Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Place a `watermark.png` image in the root directory (optional). If missing, it will proceed saving without a watermark.

## Usage

Simply run the script:

```bash
python laixot.py
```

The script will remain open in the console. You can minimize it to the background.

### Hotkeys / Controls:

- <kbd>Delete</kbd>: Initialize an area capture, then **prompts you to draw an arrow**.
- <kbd>Insert</kbd>: Initialize an area capture, **skipping the arrow** drawing phase and immediately saving the result.
- <kbd>Escape</kbd>: Cancel the capture process at any time (during snipping or drawing).
- <kbd>Enter</kbd> (in arrow drawing phase): Save without drawing an arrow.
- <kbd>Ctrl+C</kbd> (in console): Close the application entirely.

Once a selection (and optional arrow drawing) is complete, the file will be saved directly into the `./captures/` folder as `laixot_X.webp`.

## Architecture Details

- Uses `mss` for high-performance and multi-monitor accurate screen grabbing.
- Uses `Pillow` (PIL) for image manipulation, WebP encoding, and Lanczos downscaling.
- Uses `keyboard` for global system-wide hotkey listening (usually does not require admin rights, but if hotkeys are ignored, try running the terminal/cmd as Administrator).
- Uses `tkinter` (native to Python) for drawing the transparent selection overlay and the arrow preview.

## License

MIT License. Feel free to use and modify.
