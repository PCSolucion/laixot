import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import keyboard
import os
import time
import math
import ctypes
import mss
import json

# DPI awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

CONFIG_FILE = "config.json"
WATERMARK_PATH = "watermark.png"

DEFAULT_CONFIG = {
    "output_dir": "screenshots",
    "quality": 90,
    "format": "webp",
    "hotkey_arrow": "delete",
    "hotkey_no_arrow": "º"
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Merge with default to ensure all keys exist
                return {**DEFAULT_CONFIG, **config}
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def get_cursor_pos():
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

def find_monitor_for_cursor(monitors, cx, cy):
    for m in monitors[1:]:
        if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
            return m
    return monitors[1]

class SettingsWindow:
    def __init__(self, on_start_callback):
        self.on_start = on_start_callback
        self.config = load_config()
        
        self.root = tk.Tk()
        self.root.title("Configuración de Laixot")
        self.root.geometry("500x450")
        self.root.resizable(False, False)
        
        # Style
        style = ttk.Style()
        style.configure("TLabel", padding=5)
        style.configure("TButton", padding=5)
        
        main_frame = ttk.Frame(self.root, padding="25")
        main_frame.pack(fill="both", expand=True)
        main_frame.columnconfigure(1, weight=1)

        # Output Directory
        ttk.Label(main_frame, text="Carpeta de salida:").grid(row=0, column=0, sticky="w", pady=5)
        self.path_var = tk.StringVar(value=self.config["output_dir"])
        path_entry = ttk.Entry(main_frame, textvariable=self.path_var)
        path_entry.grid(row=0, column=1, sticky="ew", padx=(5, 2))
        ttk.Button(main_frame, text="...", width=3, command=self.browse_path).grid(row=0, column=2, padx=(0, 5))

        # Quality
        ttk.Label(main_frame, text="Calidad (1-100):").grid(row=1, column=0, sticky="w", pady=10)
        self.quality_var = tk.IntVar(value=self.config["quality"])
        quality_frame = ttk.Frame(main_frame)
        quality_frame.grid(row=1, column=1, columnspan=2, sticky="ew")
        quality_frame.columnconfigure(0, weight=1)
        
        ttk.Scale(quality_frame, from_=1, to=100, variable=self.quality_var, orient="horizontal").grid(row=0, column=0, sticky="ew")
        ttk.Label(quality_frame, textvariable=self.quality_var, width=3).grid(row=0, column=1, padx=5)

        # Format
        ttk.Label(main_frame, text="Formato:").grid(row=2, column=0, sticky="w", pady=5)
        self.format_var = tk.StringVar(value=self.config["format"])
        format_combo = ttk.Combobox(main_frame, textvariable=self.format_var, values=["webp", "png", "jpg"], state="readonly")
        format_combo.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5)

        # Hotkeys Section
        ttk.Separator(main_frame, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky="ew", pady=20)
        ttk.Label(main_frame, text="Atajos de Teclado", font=("", 11, "bold")).grid(row=4, column=0, columnspan=3, sticky="w")
        
        ttk.Label(main_frame, text="Con flechas:").grid(row=5, column=0, sticky="w", pady=(10, 5))
        self.hk_arrow_var = tk.StringVar(value=self.config["hotkey_arrow"])
        ttk.Entry(main_frame, textvariable=self.hk_arrow_var).grid(row=5, column=1, columnspan=2, sticky="ew", padx=5)

        ttk.Label(main_frame, text="Sin flechas:").grid(row=6, column=0, sticky="w", pady=5)
        self.hk_no_arrow_var = tk.StringVar(value=self.config["hotkey_no_arrow"])
        ttk.Entry(main_frame, textvariable=self.hk_no_arrow_var).grid(row=6, column=1, columnspan=2, sticky="ew", padx=5)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(30, 0))
        
        ttk.Button(btn_frame, text="Guardar y Ejecutar", command=self.start_app).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancelar", command=self.root.destroy).pack(side="right")

        self.root.mainloop()

    def browse_path(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.path_var.set(dir_path)

    def start_app(self):
        # Update config
        self.config["output_dir"] = self.path_var.get()
        self.config["quality"] = self.quality_var.get()
        self.config["format"] = self.format_var.get()
        self.config["hotkey_arrow"] = self.hk_arrow_var.get().lower()
        self.config["hotkey_no_arrow"] = self.hk_no_arrow_var.get().lower()
        
        save_config(self.config)
        
        new_config = self.config.copy()
        self.root.destroy()
        self.on_start(new_config)

class ScreenshotApp:
    def __init__(self, config):
        self.config = config
        self.root = tk.Tk()
        self.root.withdraw()
        self.capturing = False
        self.skip_arrow = False
        self.arrows_history = []
        self.snip_window = None
        self.arrow_window = None
        
        # Register hotkeys
        try:
            keyboard.add_hotkey(self.config["hotkey_arrow"], lambda: self.root.after(0, self._on_hotkey, False), suppress=True)
            keyboard.add_hotkey(self.config["hotkey_no_arrow"], lambda: self.root.after(0, self._on_hotkey, True), suppress=True)
            print(f"Laixot Running! '{self.config['hotkey_arrow']}': with arrows | '{self.config['hotkey_no_arrow']}': without arrows")
        except Exception as e:
            messagebox.showerror("Hotkey Error", f"No se pudo registrar la tecla: {e}")
            os._exit(1)

    def _on_hotkey(self, skip_arrow):
        if self.capturing:
            self.reset_listener()
            return
        self.capturing = True
        self.skip_arrow = skip_arrow
        self.arrows_history = []
        self.start_capture()

    def start_capture(self):
        time.sleep(0.15)
        cx, cy = get_cursor_pos()
        with mss.mss() as sct:
            monitors = sct.monitors
            self.monitor = find_monitor_for_cursor(monitors, cx, cy)
            screenshot = sct.grab(self.monitor)
            self.full_image = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            
            dark_overlay = Image.new("RGB", self.full_image.size, (20, 20, 20))
            self.dimmed_image = Image.blend(self.full_image, dark_overlay, 0.5)

        mon = self.monitor
        self.snip_window = tk.Toplevel(self.root)
        self.snip_window.overrideredirect(True)
        self.snip_window.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
        self.snip_window.attributes('-topmost', True)
        self.snip_window.focus_force()
        
        self.tk_dimmed = ImageTk.PhotoImage(self.dimmed_image)
        self.tk_full = ImageTk.PhotoImage(self.full_image)

        self.canvas = tk.Canvas(self.snip_window, cursor="cross", width=mon['width'], height=mon['height'], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_dimmed)
        
        self.selection_img_id = None
        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.snip_window.bind("<Escape>", lambda e: self.reset_listener())

    def on_button_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='white', width=1)

    def on_move_press(self, event):
        cur_x, cur_y = event.x, event.y
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
        x1, y1 = min(self.start_x, cur_x), min(self.start_y, cur_y)
        x2, y2 = max(self.start_x, cur_x), max(self.start_y, cur_y)
        
        if self.selection_img_id: self.canvas.delete(self.selection_img_id)
        if x2 - x1 > 0 and y2 - y1 > 0:
            clear_part = self.full_image.crop((x1, y1, x2, y2))
            self.tk_clear_part = ImageTk.PhotoImage(clear_part)
            self.selection_img_id = self.canvas.create_image(x1, y1, anchor=tk.NW, image=self.tk_clear_part)
            self.canvas.tag_lower(self.selection_img_id, self.rect)

    def on_button_release(self, event):
        end_x, end_y = event.x, event.y
        self.snip_window.destroy()
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.reset_listener()
            return
        self.cropped_image = self.full_image.crop((x1, y1, x2, y2))
        if self.skip_arrow: self.save_result()
        else: self.start_arrow_drawing()

    def start_arrow_drawing(self):
        self.arrow_window = tk.Toplevel(self.root)
        self.arrow_window.title("Draw - Enter/RightClick:Save | Ctrl+Z:Undo")
        self.arrow_window.attributes('-topmost', True)
        w, h = self.cropped_image.size
        self.arrow_window.geometry(f"{w}x{h}")
        self.arrows_history = []
        self.current_temp_arrow = None
        self.refresh_arrow_canvas()
        self.arrow_canvas.bind("<ButtonPress-1>", self.on_arrow_press)
        self.arrow_canvas.bind("<B1-Motion>", self.on_arrow_move)
        self.arrow_canvas.bind("<ButtonRelease-1>", self.on_arrow_release)
        self.arrow_canvas.bind("<Button-3>", lambda e: self.save_result())
        self.arrow_window.bind("<Escape>", lambda e: self.reset_listener())
        self.arrow_window.bind("<Return>", lambda e: self.save_result())
        self.arrow_window.bind("<Control-z>", lambda e: self.undo_arrow())

    def refresh_arrow_canvas(self):
        if hasattr(self, 'arrow_canvas'): self.arrow_canvas.destroy()
        w, h = self.cropped_image.size
        self.tk_canvas_img = ImageTk.PhotoImage(self.cropped_image)
        self.arrow_canvas = tk.Canvas(self.arrow_window, width=w, height=h, cursor="crosshair", highlightthickness=0)
        self.arrow_canvas.pack()
        self.arrow_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_canvas_img)
        for ax1, ay1, ax2, ay2 in self.arrows_history:
            self.arrow_canvas.create_line(ax1, ay1, ax2, ay2, arrow=tk.LAST, fill="red", width=4, arrowshape=(16, 20, 6))

    def on_arrow_press(self, event):
        self.arrow_start_x, self.arrow_start_y = event.x, event.y

    def on_arrow_move(self, event):
        if self.current_temp_arrow: self.arrow_canvas.delete(self.current_temp_arrow)
        self.current_temp_arrow = self.arrow_canvas.create_line(self.arrow_start_x, self.arrow_start_y, event.x, event.y, arrow=tk.LAST, fill="red", width=4, arrowshape=(16, 20, 6))

    def on_arrow_release(self, event):
        dist = math.hypot(event.x - self.arrow_start_x, event.y - self.arrow_start_y)
        if dist > 5: self.arrows_history.append((self.arrow_start_x, self.arrow_start_y, event.x, event.y))
        self.current_temp_arrow = None
        self.refresh_arrow_canvas()

    def undo_arrow(self):
        if self.arrows_history:
            self.arrows_history.pop()
            self.refresh_arrow_canvas()

    def _draw_arrows_to_image(self):
        if not self.arrows_history: return
        SCALE = 4
        orig_w, orig_h = self.cropped_image.size
        big = self.cropped_image.resize((orig_w * SCALE, orig_h * SCALE), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        for x1, y1, x2, y2 in self.arrows_history:
            sx1, sy1, sx2, sy2 = x1*SCALE, y1*SCALE, x2*SCALE, y2*SCALE
            head_len, angle = 22*SCALE, math.atan2(sy2-sy1, sx2-sx1)
            lx2, ly2 = sx2 - head_len*0.55*math.cos(angle), sy2 - head_len*0.55*math.sin(angle)
            draw.line([(sx1, sy1), (lx2, ly2)], fill="red", width=4*SCALE)
            p1 = (sx2 - head_len*math.cos(angle-math.pi/5.5), sy2 - head_len*math.sin(angle-math.pi/5.5))
            p2 = (sx2 - head_len*math.cos(angle+math.pi/5.5), sy2 - head_len*math.sin(angle+math.pi/5.5))
            draw.polygon([(sx2, sy2), p1, p2], fill="red")
        self.cropped_image = big.resize((orig_w, orig_h), Image.LANCZOS)

    def save_result(self):
        if not self.skip_arrow:
            self._draw_arrows_to_image()
            if self.arrow_window:
                self.arrow_window.destroy()
                self.arrow_window = None
        img = self.cropped_image.convert("RGBA")
        if os.path.exists(WATERMARK_PATH):
            watermark = Image.open(WATERMARK_PATH).convert("RGBA")
            bg_w, bg_h = img.size
            max_size = max(15, min(60, int(bg_w * 0.06)))
            watermark.thumbnail((max_size, max_size), Image.LANCZOS)
            wm_w, wm_h = watermark.size
            margin = max(5, int(bg_w * 0.01))
            img.paste(watermark, (bg_w - wm_w - margin, bg_h - wm_h - margin), watermark)

        out_dir = self.config["output_dir"]
        os.makedirs(out_dir, exist_ok=True)
        fmt = self.config["format"]
        counter = 1
        while True:
            filename = os.path.join(out_dir, f"captura_guia_{counter}.{fmt}")
            if not os.path.exists(filename): break
            counter += 1
            
        save_params = {"quality": self.config["quality"]} if fmt in ["webp", "jpg"] else {}
        img.convert("RGB").save(filename, fmt, **save_params)
        print(f"✓ Saved: {filename}")
        self.reset_listener()

    def reset_listener(self):
        for attr in ('snip_window', 'arrow_window'):
            win = getattr(self, attr, None)
            if win:
                try:
                    if win.winfo_exists(): win.destroy()
                except: pass
            setattr(self, attr, None)
        self.capturing = False

def start_main_app(config):
    app = ScreenshotApp(config)
    app.root.mainloop()

if __name__ == "__main__":
    SettingsWindow(start_main_app)


