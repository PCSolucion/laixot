import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
import keyboard
import os
import time
import math
import ctypes
import mss

# DPI awareness so coordinates match correctly with Windows scaling
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

WATERMARK_PATH = "watermark.png"
OUTPUT_DIR = "screenshots"


def get_cursor_pos():
    """Gets the real cursor position in physical pixel coordinates."""
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def find_monitor_for_cursor(monitors, cx, cy):
    """Returns the monitor (mss dict) where the cursor is located. Returns the primary one if not found."""
    for m in monitors[1:]:  # monitors[0] is the combined display (all monitors)
        if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
            return m
    return monitors[1]


class ScreenshotApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.capturing = False
        self.skip_arrow = False
        
        # Register hotkeys only once at startup
        keyboard.add_hotkey('delete', lambda: self.root.after(0, self._on_hotkey, False), suppress=True)
        keyboard.add_hotkey('º', lambda: self.root.after(0, self._on_hotkey, True), suppress=True)
        print("Waiting — 'Delete': capture with arrow | 'º': capture without arrow | Ctrl+C: exit")

    def _on_hotkey(self, skip_arrow):
        if self.capturing:
            # If already capturing, pressing the hotkey again cancels the process
            self.reset_listener()
            return
        self.capturing = True
        self.skip_arrow = skip_arrow
        self.start_capture()

    # ------------------------------------------------------------------
    # PHASE 1: Capture and area selection
    # ------------------------------------------------------------------
    def start_capture(self):
        time.sleep(0.15)

        # Detect the monitor where the cursor is currently located
        cx, cy = get_cursor_pos()
        with mss.mss() as sct:
            monitors = sct.monitors
            self.monitor = find_monitor_for_cursor(monitors, cx, cy)
            # Capture only that specific monitor
            screenshot = sct.grab(self.monitor)
            self.full_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        mon = self.monitor
        mon_x = mon["left"]
        mon_y = mon["top"]
        mon_w = mon["width"]
        mon_h = mon["height"]

        self.snip_window = tk.Toplevel(self.root)
        self.snip_window.overrideredirect(True)
        self.snip_window.geometry(f"{mon_w}x{mon_h}+{mon_x}+{mon_y}")
        self.snip_window.attributes('-topmost', True)
        self.snip_window.focus_force() # Ensure the window has focus for the Escape key to work
        
        # To "freeze" the screen and avoid brightness shifts, we show the captured image
        self.tk_full_image = ImageTk.PhotoImage(self.full_image)

        self.canvas = tk.Canvas(self.snip_window, cursor="cross",
                                 width=mon_w, height=mon_h, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_full_image)
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.snip_window.bind("<Escape>", lambda e: self.reset_listener())

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x + 1, self.start_y + 1,
            outline='red', width=2, fill=""
        )

    def on_move_press(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        self.snip_window.destroy()

        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 < 10 or y2 - y1 < 10:
            print("Selection too small, canceling...")
            self.reset_listener()
            return

        self.cropped_image = self.full_image.crop((x1, y1, x2, y2))
        if self.skip_arrow:
            self.save_result()
        else:
            self.start_arrow_drawing()

    # ------------------------------------------------------------------
    # PHASE 2: Arrow drawing on the cropped image
    # ------------------------------------------------------------------
    def start_arrow_drawing(self):
        self.arrow_window = tk.Toplevel(self.root)
        self.arrow_window.title("Draw an arrow — Escape to cancel, Drag to draw")
        self.arrow_window.attributes('-topmost', True)

        width, height = self.cropped_image.size

        self.arrow_window.geometry(f"{width}x{height}")
        self.arrow_window.resizable(False, False)

        self.tk_image = ImageTk.PhotoImage(self.cropped_image)

        self.arrow_canvas = tk.Canvas(self.arrow_window, width=width, height=height, cursor="crosshair")
        self.arrow_canvas.pack()
        self.arrow_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        self.arrow_start_x = None
        self.arrow_start_y = None
        self.current_arrow_line = None

        self.arrow_canvas.bind("<ButtonPress-1>", self.on_arrow_press)
        self.arrow_canvas.bind("<B1-Motion>", self.on_arrow_move)
        self.arrow_canvas.bind("<ButtonRelease-1>", self.on_arrow_release)
        self.arrow_window.bind("<Escape>", lambda e: self.reset_listener())
        
        # Allow saving directly without drawing an arrow by pressing Enter
        self.arrow_window.bind("<Return>", lambda e: self._finish_and_save())

    def on_arrow_press(self, event):
        self.arrow_start_x = event.x
        self.arrow_start_y = event.y
        if self.current_arrow_line:
            self.arrow_canvas.delete(self.current_arrow_line)
        self.current_arrow_line = self.arrow_canvas.create_line(
            self.arrow_start_x, self.arrow_start_y, event.x, event.y,
            arrow=tk.LAST, fill="red", width=4, arrowshape=(16, 20, 6)
        )

    def on_arrow_move(self, event):
        if self.current_arrow_line:
            self.arrow_canvas.coords(self.current_arrow_line,
                                      self.arrow_start_x, self.arrow_start_y, event.x, event.y)

    def on_arrow_release(self, event):
        end_x, end_y = event.x, event.y

        dist = math.hypot(end_x - self.arrow_start_x, end_y - self.arrow_start_y)
        if dist > 5:
            self._draw_arrow_antialiased(
                self.arrow_start_x, self.arrow_start_y, end_x, end_y
            )

        self.arrow_window.destroy()
        self.save_result()

    def _draw_arrow_antialiased(self, x1, y1, x2, y2):
        """Draws an arrow with anti-aliasing using 4x supersampling."""
        SCALE = 4
        orig_w, orig_h = self.cropped_image.size

        # Create large canvas (4x) with current image
        big = self.cropped_image.resize((orig_w * SCALE, orig_h * SCALE), Image.NEAREST)
        draw = ImageDraw.Draw(big)

        sx1, sy1 = x1 * SCALE, y1 * SCALE
        sx2, sy2 = x2 * SCALE, y2 * SCALE

        line_w  = 4 * SCALE
        head_len = 22 * SCALE
        angle = math.atan2(sy2 - sy1, sx2 - sx1)
        angle_offset = math.pi / 5.5

        # Main line (shortened to not overlap the arrowhead)
        shorten = head_len * 0.55
        lx2 = sx2 - shorten * math.cos(angle)
        ly2 = sy2 - shorten * math.sin(angle)
        draw.line([(sx1, sy1), (lx2, ly2)], fill="red", width=line_w)

        # Arrowhead (filled polygon)
        p1 = (sx2 - head_len * math.cos(angle - angle_offset),
              sy2 - head_len * math.sin(angle - angle_offset))
        p2 = (sx2 - head_len * math.cos(angle + angle_offset),
              sy2 - head_len * math.sin(angle + angle_offset))
        draw.polygon([(sx2, sy2), p1, p2], fill="red")

        # Scale back to original size with LANCZOS for smooth edges
        self.cropped_image = big.resize((orig_w, orig_h), Image.LANCZOS)

    def _finish_and_save(self):
        """Save without an arrow (if Enter is pressed in the arrow window)."""
        self.arrow_window.destroy()
        self.save_result()

    # ------------------------------------------------------------------
    # PHASE 3: Watermark and saving
    # ------------------------------------------------------------------
    def save_result(self):
        img = self.cropped_image.convert("RGBA")

        if os.path.exists(WATERMARK_PATH):
            try:
                watermark = Image.open(WATERMARK_PATH).convert("RGBA")
                bg_w, bg_h = img.size

                # Proportional size: 6% of image width (reduced by 25%), bounded min/max
                max_size = max(15, min(60, int(bg_w * 0.06)))
                watermark.thumbnail((max_size, max_size), Image.LANCZOS)
                wm_w, wm_h = watermark.size

                # Proportional margin (1% of image width, minimum 5px)
                margin = max(5, int(bg_w * 0.01))
                pos = (bg_w - wm_w - margin, bg_h - wm_h - margin)
                img.paste(watermark, pos, watermark)
            except Exception as e:
                print(f"Failed to add watermark: {e}")
        else:
            print(f"Warning: '{WATERMARK_PATH}' not found. Please place your PNG in the script folder.")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Find next available number for laixot_X.webp
        counter = 1
        while True:
            filename = os.path.join(OUTPUT_DIR, f"laixot_{counter}.webp")
            if not os.path.exists(filename):
                break
            counter += 1
            
        # quality=90 -> high quality, larger file size than 75 but better clarity
        # method=6   -> max encoder effort
        img.convert("RGB").save(filename, "webp", quality=90, method=6)
        print(f"✓ Saved: {filename}")

        self.reset_listener()

    # ------------------------------------------------------------------
    def reset_listener(self):
        for attr in ('snip_window', 'arrow_window'):
            win = getattr(self, attr, None)
            if win:
                try:
                    if win.winfo_exists():
                        win.destroy()
                except Exception:
                    pass
        self.capturing = False  # Reset flag to allow new captures


if __name__ == "__main__":
    app = ScreenshotApp()
    app.root.mainloop()
