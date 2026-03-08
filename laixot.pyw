import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import keyboard
import os
import sys
import time
import math
import ctypes
import mss
import json
import threading
import winreg
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk, ImageDraw, ImageFilter
import win32clipboard
from io import BytesIO

# Ocultar la ventana de consola negra al iniciar
try:
    hwnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0) # 0 = SW_HIDE
except Exception:
    pass

try:
    myappid = 'miapp.laixot.screenshot.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

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
                return {**DEFAULT_CONFIG, **config}
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

def check_autostart():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, "Laixot")
        winreg.CloseKey(key)
        return True
    except:
        return False

def set_autostart(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        python_exe = sys.executable
        
        # Si estamos usando python.exe, lo cambiamos a pythonw.exe para que no muestre consola al arrancar con Windows
        if python_exe.lower().endswith("python.exe"):
            pythonw = python_exe[:-10] + "pythonw.exe"
            if os.path.exists(pythonw):
                python_exe = pythonw
                
        script_path = os.path.abspath(sys.argv[0])
        cmd = f'"{python_exe}" "{script_path}"' if script_path.endswith('.py') else f'"{script_path}"'
        if enable:
            winreg.SetValueEx(key, "Laixot", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, "Laixot")
            except:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Error setting autostart: {e}")

def get_cursor_pos():
    point = ctypes.wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y

def find_monitor_for_cursor(monitors, cx, cy):
    for m in monitors[1:]:
        if m["left"] <= cx < m["left"] + m["width"] and m["top"] <= cy < m["top"] + m["height"]:
            return m
    return monitors[1]

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent, config, on_save):
        super().__init__(parent)
        self.config = config
        self.on_save = on_save
        
        self.title("Configuración de Laixot")
        self.geometry("500x550")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.after(200, lambda: self.attributes('-topmost', False))
        
        self.grid_columnconfigure(1, weight=1)

        # Title
        ctk.CTkLabel(self, text="Ajustes de Laixot", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, columnspan=3, pady=20)

        # Output Directory
        ctk.CTkLabel(self, text="Carpeta de salida:").grid(row=1, column=0, sticky="w", padx=20, pady=5)
        self.path_var = ctk.StringVar(value=self.config["output_dir"])
        ctk.CTkEntry(self, textvariable=self.path_var).grid(row=1, column=1, sticky="ew", padx=5)
        ctk.CTkButton(self, text="...", width=40, command=self.browse_path).grid(row=1, column=2, padx=20)

        # Quality
        ctk.CTkLabel(self, text="Calidad (1-100):").grid(row=2, column=0, sticky="w", padx=20, pady=10)
        self.quality_var = ctk.IntVar(value=self.config["quality"])
        qual_frame = ctk.CTkFrame(self, fg_color="transparent")
        qual_frame.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5)
        qual_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkSlider(qual_frame, from_=1, to=100, variable=self.quality_var, command=self.update_quality_label).grid(row=0, column=0, sticky="ew")
        self.quality_label = ctk.CTkLabel(qual_frame, text=str(self.quality_var.get()), width=30)
        self.quality_label.grid(row=0, column=1, padx=5)

        # Format
        ctk.CTkLabel(self, text="Formato:").grid(row=3, column=0, sticky="w", padx=20, pady=5)
        self.format_var = ctk.StringVar(value=self.config["format"])
        ctk.CTkOptionMenu(self, variable=self.format_var, values=["webp", "png", "jpg"]).grid(row=3, column=1, columnspan=2, sticky="ew", padx=5)

        # Hotkeys
        ctk.CTkLabel(self, text="Atajos de Teclado", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, columnspan=3, sticky="w", padx=20, pady=(20, 5))
        
        ctk.CTkLabel(self, text="Captura Editada:").grid(row=5, column=0, sticky="w", padx=20, pady=5)
        self.hk_arrow_var = ctk.StringVar(value=self.config["hotkey_arrow"])
        ctk.CTkEntry(self, textvariable=self.hk_arrow_var).grid(row=5, column=1, columnspan=2, sticky="ew", padx=5)

        ctk.CTkLabel(self, text="Captura Rápida:").grid(row=6, column=0, sticky="w", padx=20, pady=5)
        self.hk_no_arrow_var = ctk.StringVar(value=self.config["hotkey_no_arrow"])
        ctk.CTkEntry(self, textvariable=self.hk_no_arrow_var).grid(row=6, column=1, columnspan=2, sticky="ew", padx=5)

        # Autostart
        ctk.CTkLabel(self, text="Sistema", font=ctk.CTkFont(size=14, weight="bold")).grid(row=7, column=0, columnspan=3, sticky="w", padx=20, pady=(20, 5))
        self.autostart_var = ctk.BooleanVar(value=check_autostart())
        ctk.CTkSwitch(self, text="Iniciar con Windows", variable=self.autostart_var, command=self.toggle_autostart).grid(row=8, column=0, columnspan=3, sticky="w", padx=20, pady=5)

        # Save
        ctk.CTkButton(self, text="Guardar Cambios", command=self.save_and_close).grid(row=9, column=0, columnspan=3, pady=30)

    def update_quality_label(self, val):
        self.quality_label.configure(text=str(int(val)))

    def browse_path(self):
        d = filedialog.askdirectory()
        if d:
            self.path_var.set(d)

    def toggle_autostart(self):
        set_autostart(self.autostart_var.get())

    def save_and_close(self):
        self.config["output_dir"] = self.path_var.get()
        self.config["quality"] = int(self.quality_var.get())
        self.config["format"] = self.format_var.get()
        self.config["hotkey_arrow"] = self.hk_arrow_var.get().lower()
        self.config["hotkey_no_arrow"] = self.hk_no_arrow_var.get().lower()
        self.on_save(self.config)
        self.destroy()

class LaixotApp:
    def __init__(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.withdraw()
        self.config = load_config()
        self.capturing = False
        self.skip_tools = False
        
        self.draw_history = []
        self.current_tool = "arrow"
        
        self.snip_window = None
        self.edit_window = None
        self.settings_window = None
        
        self.register_hotkeys()
        
        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
        self.tray_thread.start()

    def register_hotkeys(self):
        keyboard.unhook_all()
        try:
            keyboard.add_hotkey(self.config["hotkey_arrow"], lambda: self.root.after(0, self.begin_capture, False), suppress=True)
            keyboard.add_hotkey(self.config["hotkey_no_arrow"], lambda: self.root.after(0, self.begin_capture, True), suppress=True)
        except Exception as e:
            print("Hotkey Error:", e)

    def setup_tray(self):
        image = Image.new('RGB', (64, 64), color=(30, 136, 229))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill=(255, 255, 255))
        draw.polygon([(24, 20), (46, 32), (24, 44)], fill=(30, 136, 229))
        
        menu = pystray.Menu(
            item('Configuración', lambda: self.root.after(0, self.show_settings)),
            item('Capturar pantalla', lambda: self.root.after(0, self.begin_capture, False)),
            item('Salir', lambda: self.root.after(0, self.quit_app))
        )
        self.icon = pystray.Icon("Laixot", image, "Laixot Screenshot Tool", menu)
        self.icon.run()

    def show_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self.root, self.config, self.on_settings_saved)
        else:
            self.settings_window.focus()

    def on_settings_saved(self, new_config):
        self.config = new_config
        save_config(self.config)
        self.register_hotkeys()

    def quit_app(self):
        self.icon.stop()
        self.root.quit()
        os._exit(0)

    def begin_capture(self, skip_tools):
        if self.capturing:
            self.reset_state()
            return
        self.capturing = True
        self.skip_tools = skip_tools
        self.draw_history = []
        
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
        self.snip_window.configure(cursor="cross")
        
        self.tk_dimmed = ImageTk.PhotoImage(self.dimmed_image)
        self.canvas = tk.Canvas(self.snip_window, width=mon['width'], height=mon['height'], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_dimmed)
        
        self.selection_img_id = None
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_snip_press)
        self.canvas.bind("<B1-Motion>", self.on_snip_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_snip_release)
        self.snip_window.bind("<Escape>", lambda e: self.reset_state())

    def on_snip_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='white', width=1)

    def on_snip_move(self, event):
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

    def on_snip_release(self, event):
        end_x, end_y = event.x, event.y
        self.snip_window.destroy()
        x1, y1 = min(self.start_x, end_x), min(self.start_y, end_y)
        x2, y2 = max(self.start_x, end_x), max(self.start_y, end_y)
        if x2 - x1 < 10 or y2 - y1 < 10:
            self.reset_state()
            return
        self.cropped_image = self.full_image.crop((x1, y1, x2, y2))
        
        if self.skip_tools:
            self.process_and_save()
        else:
            self.start_editor()

    def start_editor(self):
        self.edit_window = tk.Toplevel(self.root)
        self.edit_window.title("Laixot Editor - [A] Flecha, [R] Rectángulo, [B] Desenfocar | Enter o Click Der: Guardar")
        self.edit_window.attributes('-topmost', True)
        self.edit_window.configure(bg="#2b2b2b")
        w, h = self.cropped_image.size
        toolbar_h = 30
        self.edit_window.geometry(f"{w}x{h + toolbar_h}")
        
        self.draw_history = []
        self.current_temp_item = None
        self.current_tool = "arrow"

        self.toolbar_frame = tk.Frame(self.edit_window, bg="#1e1e1e", height=toolbar_h)
        self.toolbar_frame.pack(fill="x", side="top")
        
        self.btn_arrow = tk.Button(self.toolbar_frame, text="Flecha (A)", bg="#4caf50", fg="white", relief="flat", command=lambda: self.set_tool("arrow"))
        self.btn_arrow.pack(side="left", padx=5, pady=2)
        
        self.btn_rect = tk.Button(self.toolbar_frame, text="Rectángulo (R)", bg="#555", fg="white", relief="flat", command=lambda: self.set_tool("rect"))
        self.btn_rect.pack(side="left", padx=5, pady=2)
        
        self.btn_blur = tk.Button(self.toolbar_frame, text="Desenfocar (B)", bg="#555", fg="white", relief="flat", command=lambda: self.set_tool("blur"))
        self.btn_blur.pack(side="left", padx=5, pady=2)

        tk.Label(self.toolbar_frame, text="Enter / Click Der. = Guardar", bg="#1e1e1e", fg="#ccc").pack(side="right", padx=10)

        self.edit_canvas = tk.Canvas(self.edit_window, width=w, height=h, cursor="crosshair", highlightthickness=0, bg="gray")
        self.edit_canvas.pack(side="bottom", fill="both", expand=True)
        
        self.refresh_edit_canvas()
        
        self.edit_canvas.bind("<ButtonPress-1>", self.on_edit_press)
        self.edit_canvas.bind("<B1-Motion>", self.on_edit_move)
        self.edit_canvas.bind("<ButtonRelease-1>", self.on_edit_release)
        self.edit_canvas.bind("<Button-3>", lambda e: self.process_and_save())
        
        self.edit_window.bind("<Escape>", lambda e: self.reset_state())
        self.edit_window.bind("<Return>", lambda e: self.process_and_save())
        self.edit_window.bind("<Control-z>", lambda e: self.undo_edit())
        self.edit_window.bind("<a>", lambda e: self.set_tool("arrow"))
        self.edit_window.bind("<A>", lambda e: self.set_tool("arrow"))
        self.edit_window.bind("<r>", lambda e: self.set_tool("rect"))
        self.edit_window.bind("<R>", lambda e: self.set_tool("rect"))
        self.edit_window.bind("<b>", lambda e: self.set_tool("blur"))
        self.edit_window.bind("<B>", lambda e: self.set_tool("blur"))

    def set_tool(self, tool):
        self.current_tool = tool
        self.btn_arrow.config(bg="#4caf50" if tool=="arrow" else "#555")
        self.btn_rect.config(bg="#4caf50" if tool=="rect" else "#555")
        self.btn_blur.config(bg="#4caf50" if tool=="blur" else "#555")

    def refresh_edit_canvas(self):
        self.edit_canvas.delete("all")
        self.tk_canvas_img = ImageTk.PhotoImage(self.cropped_image)
        self.edit_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_canvas_img)
        
        for item in self.draw_history:
            tipo, x1, y1, x2, y2 = item
            if tipo == "arrow":
                self.edit_canvas.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill="red", width=4, arrowshape=(16, 20, 6))
            elif tipo == "rect":
                self.edit_canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=3)
            elif tipo == "blur":
                self.edit_canvas.create_rectangle(x1, y1, x2, y2, fill="black", stipple="gray50", outline="white")

    def on_edit_press(self, event):
        self.edit_start_x, self.edit_start_y = event.x, event.y

    def on_edit_move(self, event):
        if self.current_temp_item:
            self.edit_canvas.delete(self.current_temp_item)
        
        if self.current_tool == "arrow":
            self.current_temp_item = self.edit_canvas.create_line(self.edit_start_x, self.edit_start_y, event.x, event.y, arrow=tk.LAST, fill="red", width=4, arrowshape=(16, 20, 6))
        elif self.current_tool == "rect":
            self.current_temp_item = self.edit_canvas.create_rectangle(self.edit_start_x, self.edit_start_y, event.x, event.y, outline="red", width=3)
        elif self.current_tool == "blur":
            self.current_temp_item = self.edit_canvas.create_rectangle(self.edit_start_x, self.edit_start_y, event.x, event.y, fill="black", stipple="gray50", outline="white")

    def on_edit_release(self, event):
        dist = math.hypot(event.x - self.edit_start_x, event.y - self.edit_start_y)
        if dist > 5: 
            self.draw_history.append((self.current_tool, self.edit_start_x, self.edit_start_y, event.x, event.y))
        self.current_temp_item = None
        self.refresh_edit_canvas()

    def undo_edit(self):
        if self.draw_history:
            self.draw_history.pop()
            self.refresh_edit_canvas()

    def apply_edits_to_image(self, img):
        if not self.draw_history: return img
        SCALE = 4
        orig_w, orig_h = img.size
        
        for tipo, x1, y1, x2, y2 in self.draw_history:
            if tipo == "blur":
                bx1, by1 = min(x1, x2), min(y1, y2)
                bx2, by2 = max(x1, x2), max(y1, y2)
                box = (int(bx1), int(by1), int(bx2), int(by2))
                try:
                    icrop = img.crop(box)
                    icrop = icrop.filter(ImageFilter.GaussianBlur(15))
                    img.paste(icrop, box)
                except Exception as e:
                    print("Blur error:", e)

        big = img.resize((orig_w * SCALE, orig_h * SCALE), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        
        for item in self.draw_history:
            tipo, x1, y1, x2, y2 = item
            sx1, sy1, sx2, sy2 = x1*SCALE, y1*SCALE, x2*SCALE, y2*SCALE
            
            if tipo == "arrow":
                head_len, angle = 22*SCALE, math.atan2(sy2-sy1, sx2-sx1)
                lx2, ly2 = sx2 - head_len*0.55*math.cos(angle), sy2 - head_len*0.55*math.sin(angle)
                draw.line([(sx1, sy1), (lx2, ly2)], fill="red", width=4*SCALE)
                p1 = (sx2 - head_len*math.cos(angle-math.pi/5.5), sy2 - head_len*math.sin(angle-math.pi/5.5))
                p2 = (sx2 - head_len*math.cos(angle+math.pi/5.5), sy2 - head_len*math.sin(angle+math.pi/5.5))
                draw.polygon([(sx2, sy2), p1, p2], fill="red")
            elif tipo == "rect":
                draw.rectangle([min(sx1,sx2), min(sy1,sy2), max(sx1,sx2), max(sy1,sy2)], outline="red", width=3*SCALE)
                
        return big.resize((orig_w, orig_h), Image.LANCZOS)

    def process_and_save(self):
        if self.edit_window:
            self.edit_window.destroy()
            self.edit_window = None

        img = self.cropped_image.convert("RGBA")
        img = self.apply_edits_to_image(img)

        self.copy_to_clipboard(img)

        if os.path.exists(WATERMARK_PATH):
            try:
                watermark = Image.open(WATERMARK_PATH).convert("RGBA")
                bg_w, bg_h = img.size
                max_size = max(15, min(60, int(bg_w * 0.06)))
                watermark.thumbnail((max_size, max_size), Image.LANCZOS)
                wm_w, wm_h = watermark.size
                margin = max(5, int(bg_w * 0.01))
                img.paste(watermark, (bg_w - wm_w - margin, bg_h - wm_h - margin), watermark)
            except Exception as e:
                print("Watermark error:", e)

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
        print(f"✓ Saved: {filename} and copied to clipboard!")
        
        # Pystray notification
        if hasattr(self, 'icon'):
            self.icon.notify(f"Captura copiada! Guardada como:\n{filename}", "Laixot")

        self.reset_state()

    def copy_to_clipboard(self, image):
        try:
            output = BytesIO()
            image.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print("Failed to copy to clipboard:", e)

    def reset_state(self):
        for attr in ('snip_window', 'edit_window'):
            win = getattr(self, attr, None)
            if win:
                try:
                    if win.winfo_exists(): win.destroy()
                except: pass
            setattr(self, attr, None)
        self.capturing = False

if __name__ == "__main__":
    app = LaixotApp()
    app.root.mainloop()
