"""
Universal ROM & EEPROM Memory Editor, Backup & Flashing Studio
Organized 4-Step Professional Workflow:
1. 📥 BACKUP / EXTRACT: Create safety backup (.bak), load file, or extract directly from connected drive via VSC ATA.
2. 🛠️ EDIT & PATCH: Rosewood unlock, WD Head Map / ROYL checksums, serial/model, byte-swap, hex editing.
3. 🔍 VALIDATE: Real-time checksums, structure diagnostics, active heads and voltage safety.
4. 📤 SAVE / UPLOAD: Save patched ROM for programmer (CH341A/TL866) or flash directly back to connected drive via VSC.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import customtkinter as ctk

from core.spi_editor import UniversalROMPatcher
from core.spi_flash import UniversalMemoryInspector
from core.drive_detector import get_physical_drives
from core.vsc_engine import VSCEngine

class SPIEditorViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.patcher = None
        self.current_filepath = None
        self.current_offset = 0
        self.page_size = 512
        self.analysis_data = {}
        self.drives = []
        self.selected_drive = None

        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        # =============================================================
        # Top Workflow Bar: 4-Step Guided Toolbar
        # =============================================================
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        btn_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        btn_box.pack(fill="x", padx=10, pady=8)

        # 1. Open ROM
        self.btn_open = ctk.CTkButton(
            btn_box,
            text="📂 1. Cargar ROM / Dump",
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cmd_open_rom
        )
        self.btn_open.pack(side="left", padx=(0, 6))

        # 2. Extract Direct from Drive
        self.btn_extract = ctk.CTkButton(
            btn_box,
            text="💽 Extraer de Disco (VSC)",
            fg_color="#0d9488",
            hover_color="#0f766e",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cmd_extract_from_drive
        )
        self.btn_extract.pack(side="left", padx=6)

        # 3. Create Backup
        self.btn_backup = ctk.CTkButton(
            btn_box,
            text="🛡️ Crear Backup (.bak)",
            fg_color="#d97706",
            hover_color="#b45309",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cmd_create_backup,
            state="disabled"
        )
        self.btn_backup.pack(side="left", padx=6)

        # 4. Save Patched ROM
        self.btn_save = ctk.CTkButton(
            btn_box,
            text="💾 4. Guardar Parcheado",
            fg_color="#15803d",
            hover_color="#166534",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cmd_save_rom,
            state="disabled"
        )
        self.btn_save.pack(side="left", padx=6)

        # 5. Flash Back to Drive
        self.btn_upload = ctk.CTkButton(
            btn_box,
            text="⚡ Subir / Escribir a Disco (VSC)",
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cmd_upload_to_drive,
            state="disabled"
        )
        self.btn_upload.pack(side="left", padx=6)

        # 6. Restore Original
        self.btn_restore = ctk.CTkButton(
            btn_box,
            text="🔄 Restaurar Backup Original",
            fg_color="gray30",
            hover_color="gray40",
            font=ctk.CTkFont(size=11),
            command=self._cmd_restore_backup,
            state="disabled"
        )
        self.btn_restore.pack(side="left", padx=(6, 0))

        # Status & File Info Bar
        info_bar = ctk.CTkFrame(top_bar, fg_color="transparent")
        info_bar.pack(fill="x", padx=10, pady=(0, 8))

        self.lbl_file_info = ctk.CTkLabel(
            info_bar,
            text="Ningún archivo cargado. Abre un volcado (.bin/.rom) o extrae directamente la ROM de una unidad conectada.",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        self.lbl_file_info.pack(side="left", anchor="w")

        # Drive selector for direct VSC operations
        drive_box = ctk.CTkFrame(info_bar, fg_color="transparent")
        drive_box.pack(side="right")
        ctk.CTkLabel(drive_box, text="Unidad Destino VSC:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(0, 4))
        self.combo_drives = ctk.CTkComboBox(drive_box, values=["Escaneando..."], width=230, command=self._on_drive_selected)
        self.combo_drives.pack(side="left", padx=4)
        btn_ref_drives = ctk.CTkButton(drive_box, text="🔄", width=32, command=self.refresh_drives)
        btn_ref_drives.pack(side="left", padx=(2, 0))

        # =============================================================
        # Left Panel: Hex & ASCII Interactive Viewer & Navigator
        # =============================================================
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(left_panel, fg_color=("gray90", "gray14"), corner_radius=6)
        nav_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(nav_bar, text="Offset (Hex):", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(10, 4), pady=4)
        self.txt_offset_input = ctk.CTkEntry(nav_bar, width=100, placeholder_text="0x000000")
        self.txt_offset_input.insert(0, "0x000000")
        self.txt_offset_input.pack(side="left", padx=4, pady=4)
        self.txt_offset_input.bind("<Return>", lambda e: self._cmd_go_offset())

        btn_go_offset = ctk.CTkButton(nav_bar, text="Ir a Offset", width=80, command=self._cmd_go_offset)
        btn_go_offset.pack(side="left", padx=4, pady=4)

        btn_prev = ctk.CTkButton(nav_bar, text="◀ Anterior", width=85, command=self._cmd_prev_page)
        btn_prev.pack(side="left", padx=(8, 2), pady=4)

        btn_next = ctk.CTkButton(nav_bar, text="Siguiente ▶", width=85, command=self._cmd_next_page)
        btn_next.pack(side="left", padx=2, pady=4)

        # Search Bar
        ctk.CTkLabel(nav_bar, text="Buscar:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(12, 4), pady=4)
        self.txt_search = ctk.CTkEntry(nav_bar, width=120, placeholder_text="Texto o Hex...")
        self.txt_search.pack(side="left", padx=4, pady=4)
        self.txt_search.bind("<Return>", lambda e: self._cmd_search())

        btn_search = ctk.CTkButton(nav_bar, text="🔍 Buscar", width=70, command=self._cmd_search)
        btn_search.pack(side="left", padx=4, pady=4)

        # Hex Editor Textbox
        self.hex_editor = ctk.CTkTextbox(
            left_panel,
            font=("Consolas", 12),
            fg_color="#0a0a0a",
            text_color="#e0e7ff",
            activate_scrollbars=True
        )
        self.hex_editor.grid(row=1, column=0, sticky="nsew")
        self.hex_editor.insert("1.0", "--- Carga un archivo de volcado de memoria ROM/EEPROM (.bin / .rom / .dat) para comenzar ---")

        # =============================================================
        # Right Panel: Multi-Tab Studio (Workflow Organization)
        # =============================================================
        right_panel = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=8)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(0, weight=1)

        self.tools_tabs = ctk.CTkTabview(right_panel)
        self.tools_tabs.pack(fill="both", expand=True, padx=4, pady=4)

        tab_diag = self.tools_tabs.add("🔍 1. Diagnóstico")
        tab_patch = self.tools_tabs.add("🛠️ 2. Parcheadores")
        tab_bin = self.tools_tabs.add("⚙️ 3. Binario & Hex")
        tab_pin = self.tools_tabs.add("📌 4. Pinouts & Flasher")

        self._setup_tab_diagnostics(tab_diag)
        self._setup_tab_patchers(tab_patch)
        self._setup_tab_binary_tools(tab_bin)
        self._setup_tab_pinouts(tab_pin)

    # -------------------------------------------------------------
    # TAB 1: DIAGNOSTICS & CHIP IDENTIFICATION
    # -------------------------------------------------------------
    def _setup_tab_diagnostics(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)

        # Status & Safety Card
        status_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        status_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(status_card, text="🛡️ Estado de Seguridad & Backup:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))
        self.lbl_backup_status = ctk.CTkLabel(status_card, text="Copia de Seguridad: ❌ No creada", font=ctk.CTkFont(size=11), text_color="#ef4444")
        self.lbl_backup_status.pack(anchor="w", padx=8, pady=1)

        self.lbl_mod_status = ctk.CTkLabel(status_card, text="Estado de Edición: Sin modificaciones (Original)", font=ctk.CTkFont(size=11), text_color="#10b981")
        self.lbl_mod_status.pack(anchor="w", padx=8, pady=(1, 6))

        # Chip Profile Card
        chip_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        chip_card.pack(fill="x", padx=4, pady=4)
        chip_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(chip_card, text="📦 Identificación de Memoria:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
        
        self.lbl_diag_chip = ctk.CTkLabel(chip_card, text="Chip: No identificado", font=ctk.CTkFont(size=11))
        self.lbl_diag_chip.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=1)

        self.lbl_diag_voltage = ctk.CTkLabel(chip_card, text="Voltaje Seguro: N/A", font=ctk.CTkFont(size=11), text_color="#f59e0b")
        self.lbl_diag_voltage.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=1)

        self.lbl_diag_size = ctk.CTkLabel(chip_card, text="Tamaño Total: 0 Bytes", font=ctk.CTkFont(size=11))
        self.lbl_diag_size.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(1, 6))

        # Microcode & Drive Analysis Card
        drive_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        drive_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(drive_card, text="💽 Estructura de Microcódigo & Disco:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))

        self.lbl_diag_vendor = ctk.CTkLabel(drive_card, text="Arquitectura: Desconocida", font=ctk.CTkFont(size=11))
        self.lbl_diag_vendor.pack(anchor="w", padx=8, pady=1)

        self.lbl_diag_model = ctk.CTkLabel(drive_card, text="Modelo Detectado: -", font=ctk.CTkFont(size=11))
        self.lbl_diag_model.pack(anchor="w", padx=8, pady=1)

        self.lbl_diag_sn = ctk.CTkLabel(drive_card, text="Serial Number (SN): -", font=ctk.CTkFont(size=11))
        self.lbl_diag_sn.pack(anchor="w", padx=8, pady=1)

        self.txt_diag_details = ctk.CTkTextbox(drive_card, height=90, font=("Consolas", 10), fg_color="#0a0a0a")
        self.txt_diag_details.pack(fill="x", padx=8, pady=(4, 6))
        self.txt_diag_details.insert("1.0", "Detalles estructurales aparecerán al cargar un archivo.")

        # Cryptographic Checksums Card
        chk_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        chk_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(chk_card, text="🧮 Integridad & Checksums:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))

        self.lbl_chk_crc32 = ctk.CTkLabel(chk_card, text="CRC32: -", font=("Consolas", 10))
        self.lbl_chk_crc32.pack(anchor="w", padx=8, pady=1)

        self.lbl_chk_md5 = ctk.CTkLabel(chk_card, text="MD5: -", font=("Consolas", 10))
        self.lbl_chk_md5.pack(anchor="w", padx=8, pady=1)

        self.lbl_chk_sum16 = ctk.CTkLabel(chk_card, text="Sum 16-bit: -", font=("Consolas", 10))
        self.lbl_chk_sum16.pack(anchor="w", padx=8, pady=(1, 6))

    # -------------------------------------------------------------
    # TAB 2: BRAND PATCHERS & UNLOCKERS
    # -------------------------------------------------------------
    def _setup_tab_patchers(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. SEAGATE F3 & ROSEWOOD
        sea_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        sea_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(sea_card, text="🟢 Seagate F3 / Rosewood Tools", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10b981").pack(anchor="w", padx=8, pady=(6, 2))

        btn_unlock = ctk.CTkButton(
            sea_card,
            text="🔓 Desbloquear Terminal F3 (Rosewood Bypass)",
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._cmd_patch_unlock
        )
        btn_unlock.pack(fill="x", padx=8, pady=4)

        # Baudrate changer
        baud_frame = ctk.CTkFrame(sea_card, fg_color="transparent")
        baud_frame.pack(fill="x", padx=8, pady=(2, 6))
        ctk.CTkLabel(baud_frame, text="Baudrate UART:", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(0, 4))
        self.combo_baud = ctk.CTkOptionMenu(baud_frame, values=["115200", "460800", "921600", "38400"], width=90)
        self.combo_baud.set("115200")
        self.combo_baud.pack(side="left", padx=4)
        btn_baud = ctk.CTkButton(baud_frame, text="Parchear Baudrate", width=120, command=self._cmd_patch_baudrate)
        btn_baud.pack(side="left", padx=4)

        # 2. WESTERN DIGITAL ROYL
        wd_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        wd_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(wd_card, text="🔵 Western Digital ROYL Tools", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))

        btn_wd_chk = ctk.CTkButton(
            wd_card,
            text="🧮 Reparar Checksums Módulos ROYL",
            fg_color="#0d9488",
            hover_color="#0f766e",
            command=self._cmd_fix_wd_checksums
        )
        btn_wd_chk.pack(fill="x", padx=8, pady=4)

        head_frame = ctk.CTkFrame(wd_card, fg_color="transparent")
        head_frame.pack(fill="x", padx=8, pady=(2, 6))
        ctk.CTkLabel(head_frame, text="Aislar Cabezal Dañado:", font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(0, 4))
        self.combo_head = ctk.CTkOptionMenu(head_frame, values=["Cabezal 0", "Cabezal 1", "Cabezal 2", "Cabezal 3"], width=100)
        self.combo_head.pack(side="left", padx=4)
        btn_head = ctk.CTkButton(head_frame, text="Deshabilitar (Mod 0B)", width=130, fg_color="#d97706", hover_color="#b45309", command=self._cmd_disable_wd_head)
        btn_head.pack(side="left", padx=4)

        # 3. UNIVERSAL SERIAL & MODEL MODIFIER
        sn_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        sn_card.pack(fill="x", padx=4, pady=4)
        sn_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sn_card, text="🏷️ Modificar Número de Serie Universal:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#f59e0b").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
        self.txt_new_sn = ctk.CTkEntry(sn_card, placeholder_text="Nuevo SN (Seagate 8c, WD 12c, Tosh 10c)")
        self.txt_new_sn.grid(row=1, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")

        btn_sn = ctk.CTkButton(sn_card, text="Reemplazar", width=90, command=self._cmd_modify_sn)
        btn_sn.grid(row=1, column=1, padx=(4, 8), pady=(0, 6))

    # -------------------------------------------------------------
    # TAB 3: BINARY & CONVERSION TOOLS
    # -------------------------------------------------------------
    def _setup_tab_binary_tools(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Manual Inline Byte/Hex Writing
        edit_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        edit_card.pack(fill="x", padx=4, pady=4)
        edit_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(edit_card, text="✍️ Modificación Manual de Bytes:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))

        ctk.CTkLabel(edit_card, text="Offset (Hex):", font=ctk.CTkFont(size=10)).grid(row=1, column=0, sticky="w", padx=8, pady=(2, 0))
        self.txt_manual_offset = ctk.CTkEntry(edit_card, placeholder_text="0x000000", width=90)
        self.txt_manual_offset.grid(row=2, column=0, padx=(8, 4), pady=(0, 6), sticky="w")

        ctk.CTkLabel(edit_card, text="Bytes Hex (ej. 90 90 55 AA):", font=ctk.CTkFont(size=10)).grid(row=1, column=1, sticky="w", padx=4, pady=(2, 0))
        self.txt_manual_hex = ctk.CTkEntry(edit_card, placeholder_text="90 90 00 00")
        self.txt_manual_hex.grid(row=2, column=1, padx=4, pady=(0, 6), sticky="ew")

        btn_apply_hex = ctk.CTkButton(edit_card, text="Escribir", width=70, fg_color="#d97706", hover_color="#b45309", command=self._cmd_manual_write_hex)
        btn_apply_hex.grid(row=2, column=2, padx=(4, 8), pady=(0, 6))

        btn_undo = ctk.CTkButton(edit_card, text="↩️ Deshacer Último Cambio", fg_color="gray30", hover_color="gray40", height=24, command=self._cmd_undo_write)
        btn_undo.grid(row=3, column=0, columnspan=3, padx=8, pady=(0, 6), sticky="ew")

        # 2. Byte Swap / Endianness
        swap_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        swap_card.pack(fill="x", padx=4, pady=4)
        swap_card.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(swap_card, text="🔄 Conversión de Endianness (Byte-Swap):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))

        btn_swap16 = ctk.CTkButton(swap_card, text="Swap 16-bit (Word Swap)", command=self._cmd_swap_16)
        btn_swap16.grid(row=1, column=0, padx=(8, 4), pady=(2, 6), sticky="ew")

        btn_swap32 = ctk.CTkButton(swap_card, text="Swap 32-bit (Dword Swap)", command=self._cmd_swap_32)
        btn_swap32.grid(row=1, column=1, padx=(4, 8), pady=(2, 6), sticky="ew")

        # 3. Fill Range
        fill_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        fill_card.pack(fill="x", padx=4, pady=4)
        fill_card.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(fill_card, text="⬛ Rellenar Rango (Fill):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(6, 2))

        self.txt_fill_start = ctk.CTkEntry(fill_card, placeholder_text="Inicio (0x0)")
        self.txt_fill_start.grid(row=1, column=0, padx=(8, 4), pady=(0, 4), sticky="ew")

        self.txt_fill_end = ctk.CTkEntry(fill_card, placeholder_text="Fin (0x1000)")
        self.txt_fill_end.grid(row=1, column=1, padx=4, pady=(0, 4), sticky="ew")

        self.combo_fill_val = ctk.CTkOptionMenu(fill_card, values=["0x00 (Ceros)", "0xFF (Unos)"], width=90)
        self.combo_fill_val.grid(row=1, column=2, padx=(4, 8), pady=(0, 4), sticky="ew")

        btn_fill = ctk.CTkButton(fill_card, text="Rellenar Rango", fg_color="#b91c1c", hover_color="#991b1b", command=self._cmd_fill_range)
        btn_fill.grid(row=2, column=0, columnspan=3, padx=8, pady=(2, 6), sticky="ew")

        # 4. Pad to Standard Size
        pad_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        pad_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(pad_card, text="📏 Rellenar a Capacidad Estándar (Pad):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))

        pad_f = ctk.CTkFrame(pad_card, fg_color="transparent")
        pad_f.pack(fill="x", padx=8, pady=(0, 6))

        self.combo_pad_size = ctk.CTkOptionMenu(pad_f, values=["512 KB", "1 MB (W25Q80)", "2 MB (W25Q16)", "4 MB (W25Q32)", "8 MB (W25Q64)"])
        self.combo_pad_size.pack(side="left", padx=(0, 4))

        btn_pad = ctk.CTkButton(pad_f, text="Ajustar Tamaño (Pad 0xFF)", command=self._cmd_pad_size)
        btn_pad.pack(side="left", padx=4)

    # -------------------------------------------------------------
    # TAB 4: UNIVERSAL PINOUTS & PROGRAMMERS GUIDE
    # -------------------------------------------------------------
    def _setup_tab_pinouts(self, tab):
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=2, pady=2)
        scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll, text="📌 Guías de Conexión Universal & Programadores", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=6, pady=(4, 6))

        chip_types = {
            "SPI Flash 25xx (8-pin SOIC-8 / WSON-8)": (
                "🔌 Pinout SPI Flash 25xx (Winbond, MXIC, GigaDevice, Micron):\n"
                "• Pin 1: /CS (Chip Select - Pinza 1 / Cable Rojo)\n"
                "• Pin 2: DO / MISO (Data Out / Salida de Datos)\n"
                "• Pin 3: /WP (Write Protect - Protección contra Escritura)\n"
                "• Pin 4: GND (Tierra / Masa)\n"
                "• Pin 5: DI / MOSI (Data In / Entrada de Datos)\n"
                "• Pin 6: CLK (Serial Clock / Reloj)\n"
                "• Pin 7: /HOLD o /RESET\n"
                "• Pin 8: VCC (3.3V / 1.8V con Adaptador)\n\n"
                "⚠️ ADVERTENCIA DE VOLTAJE:\n"
                "• La mayoría de memorias modernas (Rosewood / WD USB / SSD) usan 1.8V o 3.3V.\n"
                "• ¡Nunca alimentes a 5V! Usa el adaptador de 1.8V con tu CH341A/TL866 si el chip es serie EW/FW/LQ."
            ),
            "I2C EEPROM 24Cxx (24C01 / 24C02 / 24C04 / 24C08 / 24C16...)": (
                "🔌 Pinout I2C EEPROM 24Cxx (Microchip, Atmel, ST):\n"
                "• Pin 1: A0 (Address 0 - Conectar a GND)\n"
                "• Pin 2: A1 (Address 1 - Conectar a GND)\n"
                "• Pin 3: A2 (Address 2 - Conectar a GND)\n"
                "• Pin 4: GND (Tierra)\n"
                "• Pin 5: SDA (Serial Data / Línea de Datos)\n"
                "• Pin 6: SCL (Serial Clock / Línea de Reloj)\n"
                "• Pin 7: WP (Write Protect - A GND para permitir escritura)\n"
                "• Pin 8: VCC (1.8V - 5.0V)"
            ),
            "SPI EEPROM 25Cxx / 95Cxx (25080, 25160, M95080, M95160...)": (
                "🔌 Pinout SPI EEPROM 25Cxx / 95Cxx:\n"
                "• Pin 1: /S o /CS (Chip Select)\n"
                "• Pin 2: Q o DO (Serial Data Output)\n"
                "• Pin 3: /W o /WP (Write Protect)\n"
                "• Pin 4: VSS o GND (Tierra)\n"
                "• Pin 5: D o DI (Serial Data Input)\n"
                "• Pin 6: C o SCK (Serial Clock)\n"
                "• Pin 7: /HOLD\n"
                "• Pin 8: VCC (Alimentación 3.3V - 5V)"
            ),
            "Microwire EEPROM 93Cxx (93C46, 93C56, 93C66, 93C86)": (
                "🔌 Pinout Microwire EEPROM 93Cxx (Configuración Estándar 8-pin):\n"
                "• Pin 1: CS (Chip Select - Activo en Alto)\n"
                "• Pin 2: SK (Serial Data Clock)\n"
                "• Pin 3: DI (Serial Data Input)\n"
                "• Pin 4: DO (Serial Data Output)\n"
                "• Pin 5: GND (Tierra)\n"
                "• Pin 6: ORG (Organización 8-bit / 16-bit)\n"
                "• Pin 7: NC o PE\n"
                "• Pin 8: VCC (Alimentación)"
            )
        }

        for title, text in chip_types.items():
            card = ctk.CTkFrame(scroll, fg_color=("#1e293b", "#0f172a"), corner_radius=6)
            card.pack(fill="x", padx=4, pady=4)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))
            ctk.CTkLabel(card, text=text, font=("Consolas", 10), justify="left", text_color="#cbd5e1").pack(anchor="w", padx=8, pady=(0, 8))

    # -------------------------------------------------------------
    # DRIVE DETECTION & VSC INTEGRATION
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # STEP 1: BACKUP & LOAD OPERATIONS
    # -------------------------------------------------------------
    def _cmd_open_rom(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar volcado de ROM Flash / EEPROM",
            filetypes=[
                ("Todos los volcados ROM / Binarios", "*.bin;*.rom;*.dat;*.bin8;*.hex;*.eep;*.bak"),
                ("Archivos Binarios (*.bin)", "*.bin"),
                ("Archivos ROM (*.rom)", "*.rom"),
                ("Todos los archivos", "*.*")
            ]
        )
        if not filepath:
            return

        try:
            self.patcher = UniversalROMPatcher.load_from_file(filepath)
            self.current_filepath = filepath
            self.current_offset = 0
            self.btn_save.configure(state="normal")
            self.btn_backup.configure(state="normal")
            self.btn_upload.configure(state="normal")
            self.btn_restore.configure(state="normal")

            # Automatic Safety Backup on Load
            bak_path = self.patcher.create_backup()
            self.lbl_backup_status.configure(text=f"Copia de Seguridad: ✅ Activa ({os.path.basename(bak_path)})", text_color="#10b981")

            self._update_diagnostics_and_view()
            self._log(f"Memoria cargada exitosamente: {os.path.basename(filepath)} | Backup automático creado: {os.path.basename(bak_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la memoria: {e}")

    def _cmd_extract_from_drive(self):
        """Extracts full ROM directly from connected drive via VSC ATA."""
        if not self.selected_drive:
            messagebox.showwarning("Aviso", "Selecciona una unidad de disco primero.")
            return

        drive_path = self.selected_drive.get("path")
        msg = f"¿Deseas extraer y volcar la memoria ROM directamente desde:\n{drive_path} ({self.selected_drive.get('model')}) mediante VSC ATA?"
        if not messagebox.askyesno("Extraer ROM vía VSC", msg):
            return

        try:
            vsc = VSCEngine(drive_path)
            res = vsc.wd_read_rom(num_sectors=2048)  # 1 MB
            rom_data = res.get("rom_data")
            if rom_data and len(rom_data) > 0:
                # Save to disk as extracted ROM
                save_path = filedialog.asksaveasfilename(
                    title="Guardar Volcado Extraído de ROM",
                    defaultextension=".bin",
                    initialfile=f"EXTRACTED_ROM_{self.selected_drive.get('model', 'disk').replace(' ', '_')}.bin",
                    filetypes=[("Archivo Binario (*.bin)", "*.bin"), ("Todos los archivos", "*.*")]
                )
                if save_path:
                    with open(save_path, "wb") as f:
                        f.write(rom_data)
                    self.patcher = UniversalROMPatcher.load_from_file(save_path)
                    self.current_filepath = save_path
                    self.current_offset = 0
                    self.btn_save.configure(state="normal")
                    self.btn_backup.configure(state="normal")
                    self.btn_upload.configure(state="normal")
                    self.btn_restore.configure(state="normal")

                    bak_path = self.patcher.create_backup()
                    self.lbl_backup_status.configure(text=f"Copia de Seguridad: ✅ Activa ({os.path.basename(bak_path)})", text_color="#10b981")
                    self._update_diagnostics_and_view()
                    messagebox.showinfo("Extracción Exitosa", f"ROM extraída y cargada exitosamente:\n{save_path}\n\nCopia de seguridad (.bak) creada automáticamente.")
                    self._log(f"ROM extraída vía VSC desde {drive_path} y guardada en {save_path}")
            else:
                messagebox.showerror("Error", f"No se pudo extraer la ROM: {res.get('error', 'Sin respuesta de microcódigo VSC.')}")
        except Exception as e:
            messagebox.showerror("Error al Extraer ROM", f"Excepción durante la extracción VSC: {e}")

    def _cmd_create_backup(self):
        if not self.patcher:
            return
        save_bak = filedialog.asksaveasfilename(
            title="Guardar Copia de Seguridad Original (.bak)",
            defaultextension=".bak",
            initialfile=f"BACKUP_{os.path.basename(self.current_filepath or 'rom.bin')}.bak",
            filetypes=[("Copia de Seguridad (*.bak)", "*.bak"), ("Todos los archivos", "*.*")]
        )
        if save_bak:
            bak_path = self.patcher.create_backup(save_bak)
            self.lbl_backup_status.configure(text=f"Copia de Seguridad: ✅ Activa ({os.path.basename(bak_path)})", text_color="#10b981")
            messagebox.showinfo("Backup Creado", f"Copia de seguridad guardada con éxito en:\n{bak_path}")
            self._log(f"Copia de seguridad manual creada: {bak_path}")

    def _cmd_restore_backup(self):
        if not self.patcher:
            return
        if not messagebox.askyesno("Restaurar Backup Original", "¿Deseas descartar todas las modificaciones y volver al volcado original (.bak)?"):
            return

        if self.patcher.restore_from_backup():
            self._update_diagnostics_and_view()
            messagebox.showinfo("Restauración Completa", "Se ha restaurado la memoria al estado original de fábrica.")
            self._log("Memoria restaurada desde el backup original (.bak).")
        else:
            messagebox.showwarning("Aviso", "No se encontró el archivo de copia de seguridad.")

    # -------------------------------------------------------------
    # STEP 4: SAVE & FLASH / UPLOAD TO DRIVE
    # -------------------------------------------------------------
    def _cmd_save_rom(self):
        if not self.patcher:
            return
        save_path = filedialog.asksaveasfilename(
            title="Guardar archivo ROM modificado para CH341A / Programador",
            defaultextension=".bin",
            filetypes=[("Archivo Binario (*.bin)", "*.bin"), ("Archivo ROM (*.rom)", "*.rom"), ("Todos los archivos", "*.*")],
            initialfile=f"PATCHED_{os.path.basename(self.current_filepath or 'rom.bin')}"
        )
        if save_path:
            try:
                self.patcher.save_to_file(save_path)
                messagebox.showinfo("Guardado Exitoso", f"ROM Parcheada guardada exitosamente en:\n{save_path}\n\nLista para ser programada con CH341A / RT809 / TL866.")
                self._log(f"ROM Parcheada guardada: {save_path}")
            except Exception as e:
                messagebox.showerror("Error al Guardar", f"No se pudo guardar la memoria: {e}")

    def _cmd_upload_to_drive(self):
        """Flashes / writes patched ROM directly to selected drive via VSC ATA."""
        if not self.patcher:
            messagebox.showwarning("Aviso", "Carga y parchea primero una memoria ROM.")
            return
        if not self.selected_drive:
            messagebox.showwarning("Aviso", "Selecciona una unidad de destino primero.")
            return

        drive_path = self.selected_drive.get("path")
        msg = (
            f"⚠️ ATENCIÓN: FLASHEO DIRECTO DE FIRMWARE VSC\n\n"
            f"Se escribirá y grabará la ROM modificada directamente en:\n"
            f"{drive_path} ({self.selected_drive.get('model')})\n\n"
            f"¿Estás completamente seguro de continuar con la escritura de microcódigo?"
        )
        if not messagebox.askyesno("Confirmar Flasheo VSC", msg, icon="warning"):
            return

        try:
            vsc = VSCEngine(drive_path)
            res = vsc.wd_write_rom(self.patcher.data)
            if res.get("success"):
                messagebox.showinfo("Flasheo Exitoso", f"¡ROM parcheada grabada exitosamente en la unidad {drive_path}!\n\nReinicia la alimentación del disco (Power Cycle) para aplicar cambios.")
                self._log(f"ROM parcheada grabada con éxito en {drive_path} vía VSC.")
            else:
                messagebox.showerror("Error de Flasheo", f"No se pudo escribir la ROM: {res.get('error', 'Fallo de microcódigo VSC.')}")
        except Exception as e:
            messagebox.showerror("Error al Escribir ROM", f"Excepción durante el flasheo VSC: {e}")

    # -------------------------------------------------------------
    # DIAGNOSTICS & RENDERING HELPERS
    # -------------------------------------------------------------
    def _update_diagnostics_and_view(self):
        if not self.patcher:
            return

        # Inspect
        inspector = UniversalMemoryInspector(bytes(self.patcher.data))
        self.analysis_data = inspector.analyze()

        filename = os.path.basename(self.current_filepath or "memoria.bin")
        size_str = self.analysis_data.get("size_str", "")
        vendor_type = self.analysis_data.get("vendor_type", "Desconocido")
        sn = self.analysis_data.get("serial", "N/A")

        self.lbl_file_info.configure(
            text=f"{filename} ({size_str}) | {vendor_type} | SN: {sn}",
            text_color="#38bdf8"
        )

        candidates = self.analysis_data.get("chip_candidates", [])
        chip_name = candidates[0]["model"] if candidates else "Desconocido"
        voltage = candidates[0].get("voltage", "1.8V - 3.3V") if candidates else "N/A"
        self.lbl_diag_chip.configure(text=f"Chip Compatible: {chip_name}")
        self.lbl_diag_voltage.configure(text=f"Voltaje Seguro: {voltage}")
        self.lbl_diag_size.configure(text=f"Tamaño Total: {size_str}")

        self.lbl_diag_vendor.configure(text=f"Arquitectura: {vendor_type}")
        self.lbl_diag_model.configure(text=f"Modelo Detectado: {self.analysis_data.get('model', '-')}")
        self.lbl_diag_sn.configure(text=f"Serial Number (SN): {sn}")

        chk = self.analysis_data.get("checksums", {})
        self.lbl_chk_crc32.configure(text=f"CRC32: {chk.get('crc32', '-')}")
        self.lbl_chk_md5.configure(text=f"MD5: {chk.get('md5', '-')}")
        self.lbl_chk_sum16.configure(text=f"Sum 16-bit: {chk.get('sum16', '-')}")

        details_text = "\n".join(self.analysis_data.get("details", []))
        self.txt_diag_details.delete("1.0", "end")
        self.txt_diag_details.insert("1.0", details_text or "Estructura estándar analizada correctamente.")

        # Modification status
        if self.patcher.is_modified:
            self.lbl_mod_status.configure(text="Estado de Edición: ⚠️ Modificado (Listo para guardar/flashear)", text_color="#f59e0b")
        else:
            self.lbl_mod_status.configure(text="Estado de Edición: Sin modificaciones (Original)", text_color="#10b981")

        self._render_hex_view()

    def _render_hex_view(self):
        if not self.patcher:
            return

        chunk = self.patcher.get_chunk(self.current_offset, self.page_size)
        lines = []
        header = f"{'OFFSET':<8}  {'00 01 02 03 04 05 06 07':<23}  {'08 09 0A 0B 0C 0D 0E 0F':<23}  |ASCII|"
        lines.append(header)
        lines.append("-" * len(header))

        for i in range(0, len(chunk), 16):
            sub = chunk[i:i+16]
            off_str = f"{self.current_offset + i:08X}"
            h1 = " ".join(f"{b:02X}" for b in sub[:8])
            h2 = " ".join(f"{b:02X}" for b in sub[8:])
            asc = "".join(chr(b) if 32 <= b <= 126 else "." for b in sub)
            lines.append(f"{off_str}  {h1:<23}  {h2:<23}  |{asc}|")

        self.hex_editor.delete("1.0", "end")
        self.hex_editor.insert("1.0", "\n".join(lines))
        self.txt_offset_input.delete(0, "end")
        self.txt_offset_input.insert(0, f"0x{self.current_offset:06X}")

    def _cmd_go_offset(self):
        if not self.patcher:
            return
        off_str = self.txt_offset_input.get().strip()
        try:
            new_off = int(off_str, 16) if off_str.lower().startswith("0x") else int(off_str)
            if 0 <= new_off < self.patcher.size:
                self.current_offset = (new_off // 16) * 16
                self._render_hex_view()
        except ValueError:
            messagebox.showerror("Error", "Offset hexadecimal no válido.")

    def _cmd_prev_page(self):
        if not self.patcher:
            return
        self.current_offset = max(0, self.current_offset - self.page_size)
        self._render_hex_view()

    def _cmd_next_page(self):
        if not self.patcher:
            return
        if self.current_offset + self.page_size < self.patcher.size:
            self.current_offset += self.page_size
            self._render_hex_view()

    def _cmd_search(self):
        if not self.patcher:
            return
        query = self.txt_search.get().strip()
        if not query:
            return

        try:
            if query.startswith("0x") or all(c in "0123456789ABCDEFabcdef " for c in query) and len(query.replace(" ", "")) % 2 == 0:
                pattern = bytes.fromhex(query.replace("0x", "").replace(" ", ""))
            else:
                pattern = query.encode('ascii')
        except ValueError:
            pattern = query.encode('ascii', errors='ignore')

        matches = self.patcher.search_pattern(pattern, start_offset=self.current_offset + 1)
        if not matches:
            matches = self.patcher.search_pattern(pattern, start_offset=0)

        if matches:
            found_offset = matches[0]
            self.current_offset = (found_offset // 16) * 16
            self._render_hex_view()
            self._log(f"Patrón encontrado en offset: 0x{found_offset:06X}")
        else:
            messagebox.showinfo("Búsqueda", f"No se encontró el patrón '{query}' en la memoria.")

    # -------------------------------------------------------------
    # PATCHER ACTIONS
    # -------------------------------------------------------------
    def _cmd_patch_unlock(self):
        if not self.patcher:
            messagebox.showwarning("Aviso", "Carga primero un archivo de volcado de memoria.")
            return

        res = self.patcher.find_and_patch_seagate_unlock()
        details_str = "\n".join(res.get("details", []))
        messagebox.showinfo("Resultado del Parche", f"Parche de desbloqueo aplicado:\n\n{details_str}\n\nGuarda el archivo o flashéalo con tu programador/VSC.")
        self._update_diagnostics_and_view()
        self._log(f"Parche Rosewood Unlock aplicado: {res.get('patches_applied')} modificaciones.")

    def _cmd_patch_baudrate(self):
        if not self.patcher:
            return
        target_baud = int(self.combo_baud.get())
        res = self.patcher.patch_seagate_baudrate(target_baud)
        if res.get("success"):
            messagebox.showinfo("Baudrate Actualizado", res.get("details"))
            self._update_diagnostics_and_view()
            self._log(f"Baudrate Seagate configurado a {target_baud} baud.")
        else:
            messagebox.showwarning("Aviso", res.get("error", "No se pudo cambiar el baudrate."))

    def _cmd_fix_wd_checksums(self):
        if not self.patcher:
            return
        res = self.patcher.fix_wd_royl_checksums()
        if res.get("success"):
            details_str = "\n".join(res.get("details", []))
            messagebox.showinfo("Checksums ROYL Reparados", f"Módulos corregidos: {res.get('modules_fixed')}\n\n{details_str}")
            self._update_diagnostics_and_view()
            self._log(f"Checksums ROYL reparados: {res.get('modules_fixed')} módulos.")
        else:
            messagebox.showwarning("Aviso", res.get("error", "No se encontraron módulos ROYL."))

    def _cmd_disable_wd_head(self):
        if not self.patcher:
            return
        head_str = self.combo_head.get()
        head_idx = int(head_str.split(" ")[1])
        res = self.patcher.modify_wd_head_map(head_idx)
        if res.get("success"):
            messagebox.showinfo("Cabezal Deshabilitado", res.get("details"))
            self._update_diagnostics_and_view()
            self._log(f"Cabezal {head_idx} de Western Digital deshabilitado en Mod 0B.")
        else:
            messagebox.showerror("Error", res.get("error", "No se pudo modificar el mapa de cabezales."))

    def _cmd_modify_sn(self):
        if not self.patcher:
            return
        new_sn = self.txt_new_sn.get().strip()
        if len(new_sn) < 4:
            messagebox.showerror("Error", "El número de serie ingresado es demasiado corto.")
            return

        res = self.patcher.modify_serial_number(new_sn)
        if res.get("success"):
            messagebox.showinfo("Serial Modificado", f"Se actualizó el número de serie a '{new_sn}' en {res.get('replaced_instances')} ubicaciones de la memoria.")
            self._update_diagnostics_and_view()
            self._log(f"Serial Number modificado en memoria a: {new_sn}")
        else:
            messagebox.showwarning("Aviso", "No se encontró la cadena de número de serie en formato estándar.")

    def _cmd_manual_write_hex(self):
        if not self.patcher:
            messagebox.showwarning("Aviso", "Carga primero un archivo de volcado de memoria.")
            return

        off_str = self.txt_manual_offset.get().strip()
        hex_str = self.txt_manual_hex.get().strip()

        if not off_str or not hex_str:
            messagebox.showerror("Error", "Debes ingresar un Offset y la secuencia Hexadecimal.")
            return

        try:
            offset = int(off_str, 16) if off_str.lower().startswith("0x") else int(off_str)
        except ValueError:
            messagebox.showerror("Error", "Offset no válido.")
            return

        res = self.patcher.write_hex_string(offset, hex_str)
        if res.get("success"):
            self.current_offset = (offset // 16) * 16
            self._update_diagnostics_and_view()
            self._log(f"Escritos {res.get('bytes_written')} bytes en offset 0x{offset:06X}: {hex_str}")
        else:
            messagebox.showerror("Error de Escritura", res.get("error", "Error desconocido."))

    def _cmd_undo_write(self):
        if not self.patcher:
            return
        if self.patcher.undo_last_write():
            self._update_diagnostics_and_view()
            self._log("Último cambio revertido exitosamente.")
        else:
            messagebox.showinfo("Deshacer", "No hay cambios previos en el historial para deshacer.")

    def _cmd_swap_16(self):
        if not self.patcher:
            return
        res = self.patcher.byte_swap_16bit()
        self._update_diagnostics_and_view()
        messagebox.showinfo("Byte-Swap", res.get("details"))
        self._log(res.get("details"))

    def _cmd_swap_32(self):
        if not self.patcher:
            return
        res = self.patcher.byte_swap_32bit()
        self._update_diagnostics_and_view()
        messagebox.showinfo("Byte-Swap", res.get("details"))
        self._log(res.get("details"))

    def _cmd_fill_range(self):
        if not self.patcher:
            return
        try:
            s_str = self.txt_fill_start.get().strip()
            e_str = self.txt_fill_end.get().strip()
            start_off = int(s_str, 16) if s_str.lower().startswith("0x") else int(s_str)
            end_off = int(e_str, 16) if e_str.lower().startswith("0x") else int(e_str)
            fill_byte = 0x00 if "0x00" in self.combo_fill_val.get() else 0xFF

            res = self.patcher.fill_range(start_off, end_off, fill_byte)
            if res.get("success"):
                self.current_offset = (start_off // 16) * 16
                self._update_diagnostics_and_view()
                self._log(f"Rango 0x{start_off:06X} - 0x{end_off:06X} rellenado con {res.get('fill_byte')}.")
            else:
                messagebox.showerror("Error", res.get("error"))
        except Exception as e:
            messagebox.showerror("Error", f"Valores de rango no válidos: {e}")

    def _cmd_pad_size(self):
        if not self.patcher:
            return
        size_map = {
            "512 KB": 512 * 1024,
            "1 MB (W25Q80)": 1024 * 1024,
            "2 MB (W25Q16)": 2048 * 1024,
            "4 MB (W25Q32)": 4096 * 1024,
            "8 MB (W25Q64)": 8192 * 1024
        }
        target_size = size_map.get(self.combo_pad_size.get(), 1024 * 1024)
        res = self.patcher.pad_to_standard_size(target_size)
        if res.get("success"):
            self._update_diagnostics_and_view()
            messagebox.showinfo("Pad Completado", f"Tamaño expandido de {res.get('old_size'):,} bytes a {res.get('new_size'):,} bytes (con 0xFF).")
            self._log(f"Memoria expandida a {res.get('new_size')} bytes.")
        else:
            messagebox.showwarning("Aviso", res.get("error"))

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[MEMORY-STUDIO] {text}")
