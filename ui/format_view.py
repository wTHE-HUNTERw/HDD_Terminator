"""
Real-Time Low-Level Format & Surface Scan View
Includes speed telemetry, ETA, interactive visual sector block map (Victoria / MHDD style).
"""

import threading
import time
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from core.drive_detector import get_physical_drives
from core.format_engine import LowLevelFormatEngine

class FormatViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.drives = []
        self.selected_drive = None
        self.format_engine = None

        self.block_colors = {
            "ok": "#10b981",       # Green: fast
            "slow": "#f59e0b",     # Orange/Yellow: slow
            "bad": "#ef4444",      # Red: bad sector
            "empty": "#1f2937"     # Dark gray: pending
        }

        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Top Bar: Drive Selector & Settings
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="Unidad a Formatear:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 4), pady=8)
        self.combo_drives = ctk.CTkComboBox(top_bar, values=["Escaneando..."], command=self._on_drive_selected, width=320)
        self.combo_drives.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

        btn_refresh = ctk.CTkButton(top_bar, text="🔄", width=36, command=self.refresh_drives)
        btn_refresh.grid(row=0, column=2, padx=(4, 10), pady=8)

        # Configuration Panel
        cfg_panel = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=8)
        cfg_panel.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        cfg_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Format Mode
        ctk.CTkLabel(cfg_panel, text="Modo de Operación:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")
        self.combo_mode = ctk.CTkOptionMenu(
            cfg_panel,
            values=[
                "Zero-Fill (Llenado de Ceros)",
                "Random Pattern (Sobreescritura Aleatoria)",
                "DoD 5220.22-M (3 Pasadas Certificadas)",
                "Gutmann (35 Pasadas Máxima Seguridad)",
                "Surface Read Scan (Escaneo sin borrar)",
            ]
        )
        self.combo_mode.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

        # Block Size
        ctk.CTkLabel(cfg_panel, text="Tamaño de Bloque:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, padx=10, pady=(6, 2), sticky="w")
        self.combo_block = ctk.CTkOptionMenu(
            cfg_panel,
            values=[
                "Automático (Recomendado)",
                "128 Sectores (64 KB)",
                "256 Sectores (128 KB)",
                "512 Sectores (256 KB)",
                "1024 Sectores (512 KB)",
                "2048 Sectores (1 MB)",
                "4096 Sectores (2 MB)"
            ]
        )
        self.combo_block.set("Automático (Recomendado)")
        self.combo_block.grid(row=1, column=1, padx=10, pady=(0, 8), sticky="ew")

        # Start LBA
        ctk.CTkLabel(cfg_panel, text="LBA Inicial:", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=2, padx=10, pady=(6, 2), sticky="w")
        self.txt_start_lba = ctk.CTkEntry(cfg_panel)
        self.txt_start_lba.insert(0, "0")
        self.txt_start_lba.grid(row=1, column=2, padx=10, pady=(0, 8), sticky="ew")

        # End LBA
        ctk.CTkLabel(cfg_panel, text="LBA Final (0 = Fin de Disco):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=3, padx=10, pady=(6, 2), sticky="w")
        self.txt_end_lba = ctk.CTkEntry(cfg_panel)
        self.txt_end_lba.insert(0, "0")
        self.txt_end_lba.grid(row=1, column=3, padx=10, pady=(0, 8), sticky="ew")

        # Middle Dashboard: Telemetry & Controls
        dash_frame = ctk.CTkFrame(self, fg_color="transparent")
        dash_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        dash_frame.grid_columnconfigure(0, weight=3)
        dash_frame.grid_columnconfigure(1, weight=1)
        dash_frame.grid_rowconfigure(1, weight=1)

        # Telemetry Card
        telem_card = ctk.CTkFrame(dash_frame, fg_color=("#1f2937", "#0f172a"), corner_radius=8)
        telem_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        telem_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_progress_pct = ctk.CTkLabel(telem_card, text="0.0%", font=ctk.CTkFont(size=22, weight="bold"), text_color="#38bdf8")
        self.lbl_progress_pct.grid(row=0, column=0, padx=10, pady=(6, 0))
        ctk.CTkLabel(telem_card, text="Progreso General", font=ctk.CTkFont(size=10), text_color="gray70").grid(row=1, column=0, pady=(0, 6))

        self.lbl_speed = ctk.CTkLabel(telem_card, text="0.0 MB/s", font=ctk.CTkFont(size=20, weight="bold"), text_color="#34d399")
        self.lbl_speed.grid(row=0, column=1, padx=10, pady=(6, 0))
        ctk.CTkLabel(telem_card, text="Velocidad de Escritura", font=ctk.CTkFont(size=10), text_color="gray70").grid(row=1, column=1, pady=(0, 6))

        self.lbl_eta = ctk.CTkLabel(telem_card, text="--:--", font=ctk.CTkFont(size=20, weight="bold"), text_color="#fbbf24")
        self.lbl_eta.grid(row=0, column=2, padx=10, pady=(6, 0))
        ctk.CTkLabel(telem_card, text="Tiempo Restante (ETA)", font=ctk.CTkFont(size=10), text_color="gray70").grid(row=1, column=2, pady=(0, 6))

        self.lbl_lba_status = ctk.CTkLabel(telem_card, text="LBA: 0 / 0", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_lba_status.grid(row=0, column=3, padx=10, pady=(6, 0))
        self.lbl_status_msg = ctk.CTkLabel(telem_card, text="Listo para iniciar", font=ctk.CTkFont(size=10), text_color="gray70")
        self.lbl_status_msg.grid(row=1, column=3, pady=(0, 6))

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(telem_card, height=12)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=2, column=0, columnspan=4, sticky="ew", padx=12, pady=(2, 10))

        # Visual Block Grid Map (Canvas)
        map_frame = ctk.CTkFrame(dash_frame, fg_color=("gray90", "gray14"), corner_radius=8)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=2)
        map_frame.grid_columnconfigure(0, weight=1)
        map_frame.grid_rowconfigure(1, weight=1)

        # Legend header
        legend_bar = ctk.CTkFrame(map_frame, fg_color="transparent")
        legend_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=4)
        
        ctk.CTkLabel(legend_bar, text="🗺️ Mapa de Superficie en Tiempo Real:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=4)
        
        ctk.CTkLabel(legend_bar, text="■ Rápido (<50ms)", text_color="#10b981", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=8)
        ctk.CTkLabel(legend_bar, text="■ Lento (>500ms)", text_color="#f59e0b", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=8)
        ctk.CTkLabel(legend_bar, text="■ Sector Dañado / Bad", text_color="#ef4444", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=8)

        self.canvas_map = tk.Canvas(map_frame, bg="#111827", highlightthickness=0)
        self.canvas_map.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)
        self.canvas_map.bind("<Configure>", lambda e: self._init_block_grid())

        # Action Buttons Panel (Right column)
        btn_panel = ctk.CTkFrame(dash_frame, fg_color=("gray90", "gray14"), corner_radius=8)
        btn_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=2)
        btn_panel.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(btn_panel, text="Control de Ejecución", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=10)

        self.btn_start = ctk.CTkButton(
            btn_panel,
            text="🚀 Iniciar Formateo",
            fg_color="#dc2626",
            hover_color="#991b1b",
            height=36,
            command=self._cmd_start_format
        )
        self.btn_start.pack(fill="x", padx=10, pady=6)

        self.btn_pause = ctk.CTkButton(
            btn_panel,
            text="⏸️ Pausar",
            fg_color="#d97706",
            hover_color="#b45309",
            height=32,
            command=self._cmd_toggle_pause
        )
        self.btn_pause.pack(fill="x", padx=10, pady=6)

        self.btn_stop = ctk.CTkButton(
            btn_panel,
            text="🛑 Detener / Cancelar",
            fg_color="gray30",
            hover_color="gray40",
            height=32,
            command=self._cmd_stop
        )
        self.btn_stop.pack(fill="x", padx=10, pady=6)

        # Defect counters summary card
        self.lbl_bad_count = ctk.CTkLabel(
            btn_panel,
            text="Sectores Dañados: 0\nSectores Lentos: 0\nBloques OK: 0",
            font=("Consolas", 11),
            justify="left",
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            padx=10,
            pady=8
        )
        self.lbl_bad_count.pack(fill="x", padx=10, pady=(15, 10))

        self.total_grid_blocks = 300
        self.grid_rects = []
        self.stats = {"ok": 0, "slow": 0, "bad": 0}

    def _init_block_grid(self):
        self.canvas_map.delete("all")
        self.grid_rects.clear()

        w = self.canvas_map.winfo_width()
        h = self.canvas_map.winfo_height()
        if w <= 10 or h <= 10:
            return

        cols = 30
        rows = 12
        self.total_grid_blocks = cols * rows
        
        bw = (w - (cols + 1) * 2) / cols
        bh = (h - (rows + 1) * 2) / rows

        for r in range(rows):
            for c in range(cols):
                x1 = 2 + c * (bw + 2)
                y1 = 2 + r * (bh + 2)
                x2 = x1 + bw
                y2 = y1 + bh
                rect_id = self.canvas_map.create_rectangle(x1, y1, x2, y2, fill="#1f2937", outline="#374151")
                self.grid_rects.append(rect_id)

    def refresh_drives(self):
        self.drives = get_physical_drives()
        combo_values = [f"{d['path']} - {d['model']} ({d['size_str']})" for d in self.drives]
        if not combo_values:
            combo_values = ["No hay discos detectados"]
        self.combo_drives.configure(values=combo_values)
        self.combo_drives.set(combo_values[0])
        self._on_drive_selected(combo_values[0])

    def _on_drive_selected(self, choice):
        if not self.drives:
            return
        selected_index = self.combo_drives.cget("values").index(choice) if choice in self.combo_drives.cget("values") else 0
        if selected_index < len(self.drives):
            self.selected_drive = self.drives[selected_index]
            drive_path = self.selected_drive.get("path")
            self.format_engine = LowLevelFormatEngine(
                drive_path,
                update_callback=self._on_format_progress,
                block_status_callback=self._on_block_status
            )
            # Pre-fill total sectors
            size_bytes = self.selected_drive.get("size_bytes", 0)
            total_sec = size_bytes // 512 if size_bytes > 0 else 0
            self.txt_end_lba.delete(0, "end")
            self.txt_end_lba.insert(0, str(total_sec))

    def _calculate_auto_block_size(self) -> int:
        """Calcula el tamaño de bloque óptimo en sectores según la capacidad del disco."""
        if not self.selected_drive:
            return 256
        size_bytes = self.selected_drive.get("size_bytes", 0)
        size_gb = size_bytes / (1024 ** 3)
        if size_gb >= 250:
            return 2048  # 1 MB
        elif size_gb >= 64:
            return 1024  # 512 KB
        elif size_gb >= 8:
            return 512   # 256 KB
        else:
            return 256   # 128 KB

    def _cmd_start_format(self):
        if not self.format_engine:
            return

        # Confirm critical destructive operation if write mode
        mode_str = self.combo_mode.get()
        is_write = "Scan" not in mode_str
        if is_write:
            msg = (
                f"⚠️ ATENCIÓN: ¡ESTA OPERACIÓN ES DESTRUCTIVA!\n\n"
                f"Se sobreescribirán todos los datos en {self.selected_drive.get('path')} ({self.selected_drive.get('model')}).\n"
                f"Todos los archivos, tablas de partición y sistemas de archivos se ELIMINARÁN permanentemente.\n\n"
                f"¿Estás completamente seguro de continuar con el Formateo a Bajo Nivel?"
            )
            if not messagebox.askyesno("Confirmación de Formateo a Bajo Nivel", msg, icon="warning"):
                return

        # Parse inputs
        try:
            start_lba = int(self.txt_start_lba.get().strip())
            end_lba = int(self.txt_end_lba.get().strip())
            
            block_str = self.combo_block.get()
            if "Auto" in block_str or "auto" in block_str.lower():
                block_sectors = self._calculate_auto_block_size()
                block_kb = (block_sectors * 512) // 1024
                self._log(f"Tamaño de bloque Automático seleccionado: {block_sectors} sectores ({block_kb} KB)")
            else:
                block_sectors = int(block_str.split(" ")[0])
        except ValueError:
            messagebox.showerror("Error", "Los valores de LBA o bloque no son válidos.")
            return

        mode_code = "zero"
        if "Random" in mode_str:
            mode_code = "random"
        elif "DoD" in mode_str:
            mode_code = "dod"
        elif "Gutmann" in mode_str:
            mode_code = "gutmann"
        elif "Scan" in mode_str:
            mode_code = "verify_read"

        # Reset stats and visual grid
        self.stats = {"ok": 0, "slow": 0, "bad": 0}
        self._init_block_grid()

        total_sec = self.selected_drive.get("size_bytes", 0) // 512
        if end_lba <= 0:
            end_lba = total_sec

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(text="⏸️ Pausar", fg_color="#d97706")

        self.format_engine.start_format(
            mode=mode_code,
            start_lba=start_lba,
            end_lba=end_lba,
            block_size_sectors=block_sectors,
            total_sectors=total_sec
        )
        self._log(f"Iniciando Formateo de Bajo Nivel ({mode_code.upper()}) en {self.selected_drive.get('path')} desde LBA {start_lba:,} hasta {end_lba:,}")

    def _cmd_toggle_pause(self):
        if not self.format_engine or not self.format_engine.is_running:
            return
        if self.format_engine.is_paused:
            self.format_engine.resume()
            self.btn_pause.configure(text="⏸️ Pausar", fg_color="#d97706")
            self._log("Formateo reanudado.")
        else:
            self.format_engine.pause()
            self.btn_pause.configure(text="▶️ Continuar", fg_color="#10b981")
            self._log("Formateo pausado.")

    def _cmd_stop(self):
        if self.format_engine and self.format_engine.is_running:
            self.format_engine.stop()
            self._log("Solicitando cancelación de formateo...")

    def _on_format_progress(self, lba_cur, lba_total, speed_mb_s, percent, eta_str, status_msg):
        self.lbl_progress_pct.configure(text=f"{percent:.1f}%")
        self.progress_bar.set(percent / 100.0)
        self.lbl_speed.configure(text=f"{speed_mb_s:.1f} MB/s")
        self.lbl_eta.configure(text=eta_str)
        self.lbl_lba_status.configure(text=f"LBA: {lba_cur:,} / {lba_total:,}")
        self.lbl_status_msg.configure(text=status_msg)

        if not self.format_engine.is_running:
            self.btn_start.configure(state="normal")

    def _on_block_status(self, block_index, status_type, current_lba):
        self.stats[status_type] = self.stats.get(status_type, 0) + 1
        
        # Map block index to canvas grid
        if self.grid_rects and len(self.grid_rects) > 0:
            target_idx = int((block_index * 13) % len(self.grid_rects))
            rect_id = self.grid_rects[target_idx]
            color = self.block_colors.get(status_type, "#10b981")
            self.canvas_map.itemconfig(rect_id, fill=color)

        self.lbl_bad_count.configure(
            text=f"Sectores Dañados: {self.stats.get('bad', 0)}\nSectores Lentos: {self.stats.get('slow', 0)}\nBloques OK: {self.stats.get('ok', 0)}"
        )

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[FORMAT-LLF] {text}")
