"""
Main Application Window - HDD Terminator
"""

import ctypes
import os
import sys
import tkinter as tk
from datetime import datetime
import customtkinter as ctk

from ui.overview_view import OverviewViewFrame
from ui.ata_view import ATAViewFrame
from ui.format_view import FormatViewFrame
from ui.serial_view import SerialViewFrame
from ui.vsc_view import VSCViewFrame
from ui.spi_view import SPIEditorViewFrame

def is_user_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

class HDDTerminatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HDD Terminator Ultimate - Suite Universal de Reparación, LLF & Modding SPI")
        self.geometry("1180x800")
        self.minsize(1050, 700)

        # Set cyber dark appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.pending_logs = []
        self._setup_header()
        self._setup_footer()
        self._setup_body()

        # Flush pending logs if any
        for msg in self.pending_logs:
            self._log_direct(msg)
        self.pending_logs.clear()

        # Check admin privileges
        if not is_user_admin():
            self.log_event("⚠️ ADVERTENCIA: La aplicación no se está ejecutando como Administrador. Para acceder a \\\\.\\PhysicalDriveX (Case USB), Windows requiere permisos de Administrador.")

    def _setup_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=("#111827", "#0b0f19"), height=60, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew")
        header_frame.grid_columnconfigure(1, weight=1)

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="⚡ HDD TERMINATOR ULTIMATE",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Herramienta Universal: ATA USB | Formateo en Vivo | Firmware UART | Editor Universal ROM & EEPROM",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        subtitle_lbl.grid(row=0, column=1, padx=10, pady=12, sticky="w")

        # Admin Badge
        is_admin = is_user_admin()
        badge_text = "ADMINISTRADOR (Acceso RAW OK)" if is_admin else "MODO USUARIO (Requiere Admin)"
        badge_color = "#15803d" if is_admin else "#b91c1c"
        
        admin_badge = ctk.CTkLabel(
            header_frame,
            text=badge_text,
            fg_color=badge_color,
            corner_radius=6,
            font=ctk.CTkFont(size=11, weight="bold"),
            padx=10,
            pady=4
        )
        admin_badge.grid(row=0, column=2, padx=20, pady=12)

    def _setup_body(self):
        self.main_tabs = ctk.CTkTabview(self)
        self.main_tabs.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        tab_over = self.main_tabs.add("🏠 Centro de Control & Salud")
        tab_ata = self.main_tabs.add("💽 Diagnóstico SMART & ATA")
        tab_format = self.main_tabs.add("🧹 Formateo a Bajo Nivel (En Vivo)")
        tab_vsc = self.main_tabs.add("🧪 Laboratorio por Marcas (VSC)")
        tab_spi = self.main_tabs.add("💾 Editor Universal de Memorias (ROM/EEPROM)")
        tab_serial = self.main_tabs.add("🔌 Terminal Serial de Firmware")

        # 1. Overview
        tab_over.grid_columnconfigure(0, weight=1)
        tab_over.grid_rowconfigure(0, weight=1)
        self.overview_view = OverviewViewFrame(tab_over, log_callback=self.log_event, on_navigate=self._on_navigate_tab)
        self.overview_view.grid(row=0, column=0, sticky="nsew")

        # 2. ATA
        tab_ata.grid_columnconfigure(0, weight=1)
        tab_ata.grid_rowconfigure(0, weight=1)
        self.ata_view = ATAViewFrame(tab_ata, log_callback=self.log_event)
        self.ata_view.grid(row=0, column=0, sticky="nsew")

        # 3. Format
        tab_format.grid_columnconfigure(0, weight=1)
        tab_format.grid_rowconfigure(0, weight=1)
        self.format_view = FormatViewFrame(tab_format, log_callback=self.log_event)
        self.format_view.grid(row=0, column=0, sticky="nsew")

        # 4. VSC Laboratory
        tab_vsc.grid_columnconfigure(0, weight=1)
        tab_vsc.grid_rowconfigure(0, weight=1)
        self.vsc_view = VSCViewFrame(tab_vsc, log_callback=self.log_event)
        self.vsc_view.grid(row=0, column=0, sticky="nsew")

        # 5. SPI & Universal Memory Studio
        tab_spi.grid_columnconfigure(0, weight=1)
        tab_spi.grid_rowconfigure(0, weight=1)
        self.spi_view = SPIEditorViewFrame(tab_spi, log_callback=self.log_event)
        self.spi_view.grid(row=0, column=0, sticky="nsew")

        # 6. Serial UART Terminal
        tab_serial.grid_columnconfigure(0, weight=1)
        tab_serial.grid_rowconfigure(0, weight=1)
        self.serial_view = SerialViewFrame(tab_serial, log_callback=self.log_event)
        self.serial_view.grid(row=0, column=0, sticky="nsew")

        # Setup callbacks on overview
        self.overview_view.on_drive_changed_callback = self._on_global_drive_selected
        self.overview_view.on_refresh_callback = self._refresh_all_drives

        # Initial drive scan
        self._refresh_all_drives()

    def _refresh_all_drives(self):
        from core.drive_detector import get_physical_drives
        drives = get_physical_drives()
        self.drives = drives
        self.overview_view.update_drive_list(drives)
        self.ata_view.refresh_drives()
        self.format_view.refresh_drives()
        self.vsc_view.refresh_drives()
        self.spi_view.refresh_drives()
        self.log_event(f"🔄 Lista de unidades físicas actualizada ({len(drives)} detectadas).")

    def _on_global_drive_selected(self, drive_dict):
        path = drive_dict.get("path")
        # Sync ATA view
        vals = self.ata_view.drive_combo.cget("values")
        for v in vals:
            if path in v:
                self.ata_view.drive_combo.set(v)
                self.ata_view._on_drive_selected(v)
                break

        # Sync Format view
        f_vals = self.format_view.combo_drives.cget("values")
        for v in f_vals:
            if path in v:
                self.format_view.combo_drives.set(v)
                self.format_view._on_drive_selected(v)
                break

        # Sync VSC view
        v_vals = self.vsc_view.combo_drives.cget("values")
        for v in v_vals:
            if path in v:
                self.vsc_view.combo_drives.set(v)
                self.vsc_view._on_drive_selected(v)
                break

        # Sync SPI / Memory Studio view
        s_vals = self.spi_view.combo_drives.cget("values")
        for v in s_vals:
            if path in v:
                self.spi_view.combo_drives.set(v)
                self.spi_view._on_drive_selected(v)
                break

        self.log_event(f"💽 Disco seleccionado globalmente: {path} ({drive_dict.get('model')})")

    def _on_navigate_tab(self, target: str):
        mapping = {
            "smart": "💽 Diagnóstico SMART & ATA",
            "format": "🧹 Formateo a Bajo Nivel (En Vivo)",
            "serial": "🔌 Terminal Serial de Firmware",
            "reset": "🧪 Laboratorio por Marcas (VSC)",
            "vsc": "🧪 Laboratorio por Marcas (VSC)",
            "sanitize": "🧪 Laboratorio por Marcas (VSC)",
            "spi": "💾 Editor Universal de Memorias (ROM/EEPROM)"
        }
        tab_name = mapping.get(target)
        if tab_name:
            self.main_tabs.set(tab_name)

    def _setup_footer(self):
        # 1. Resizable Splitter / Grab Bar (Row 2)
        self.splitter_bar = ctk.CTkFrame(self, fg_color=("#1e293b", "#0f172a"), height=8, corner_radius=0, cursor="sb_v_double_arrow")
        self.splitter_bar.grid(row=2, column=0, sticky="ew")
        
        # Bind drag events to resize the console
        self.splitter_bar.bind("<Button-1>", self._on_splitter_press)
        self.splitter_bar.bind("<B1-Motion>", self._on_splitter_drag)

        # 2. Console Footer Frame (Row 3)
        self.footer_frame = ctk.CTkFrame(self, fg_color=("gray90", "#0b0f19"), corner_radius=0)
        self.footer_frame.grid(row=3, column=0, sticky="nsew")
        self.footer_frame.grid_columnconfigure(0, weight=1)
        self.footer_frame.grid_rowconfigure(1, weight=1)

        # Header of the console panel with controls
        ctrl_bar = ctk.CTkFrame(self.footer_frame, fg_color="transparent", height=26)
        ctrl_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(2, 2))
        ctrl_bar.grid_columnconfigure(0, weight=1)

        lbl_log = ctk.CTkLabel(
            ctrl_bar,
            text="💻 Consola de Registro de Comandos & Eventos (Arrastra la barra superior ↕️ para cambiar tamaño):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_log.grid(row=0, column=0, sticky="w")

        btn_min = ctk.CTkButton(
            ctrl_bar,
            text="🔽 Ocultar",
            width=65,
            height=20,
            font=ctk.CTkFont(size=10),
            fg_color="gray30",
            command=lambda: self.set_console_height(35)
        )
        btn_min.grid(row=0, column=1, padx=2)

        btn_norm = ctk.CTkButton(
            ctrl_bar,
            text="↕️ Normal",
            width=65,
            height=20,
            font=ctk.CTkFont(size=10),
            fg_color="#0284c7",
            command=lambda: self.set_console_height(100)
        )
        btn_norm.grid(row=0, column=2, padx=2)

        btn_exp = ctk.CTkButton(
            ctrl_bar,
            text="🔼 Expandir",
            width=75,
            height=20,
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#15803d",
            command=lambda: self.set_console_height(260)
        )
        btn_exp.grid(row=0, column=3, padx=2)

        btn_clear = ctk.CTkButton(
            ctrl_bar,
            text="🧹 Limpiar",
            width=65,
            height=20,
            font=ctk.CTkFont(size=10),
            fg_color="gray25",
            command=self._clear_global_log
        )
        btn_clear.grid(row=0, column=4, padx=(2, 0))

        # Textbox for console logs
        self.console_height = 95
        self.global_log = ctk.CTkTextbox(
            self.footer_frame,
            height=self.console_height,
            font=("Consolas", 10),
            fg_color=("#ffffff", "#030712"),
            text_color=("#111827", "#10b981"),
            activate_scrollbars=True
        )
        self.global_log.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))

    def _on_splitter_press(self, event):
        self._drag_start_y = event.y_root
        self._drag_start_height = self.global_log.cget("height")

    def _on_splitter_drag(self, event):
        delta = self._drag_start_y - event.y_root
        new_height = max(35, min(450, self._drag_start_height + delta))
        self.set_console_height(new_height)

    def set_console_height(self, height: int):
        self.console_height = height
        self.global_log.configure(height=height)

    def _clear_global_log(self):
        self.global_log.delete("1.0", "end")

    def log_event(self, message: str):
        time_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{time_str}] {message}\n"
        if hasattr(self, "global_log"):
            self.after(0, self._log_direct, formatted)
        else:
            self.pending_logs.append(formatted)

    def _log_direct(self, formatted_message: str):
        if hasattr(self, "global_log"):
            self.global_log.insert("end", formatted_message)
            self.global_log.see("end")
