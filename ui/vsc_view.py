"""
Vendor Specific Commands & Brand-Specific Laboratory View
Fully functional buttons for ALL manufacturers with 1-Click Auto Reset:
  - Western Digital (SuperOn, Modules 0x21/0x32/0x33/0x47, Read/Backup, 1-Click)
  - Seagate (VSC via ATA + Serial instructions)
  - Samsung (Enter SA, Clear SMART/G-List, 1-Click)
  - Toshiba (Service Mode, Clear SMART/G-List, 1-Click)
  - Hitachi / HGST (NV-RAM SMART, Clear G-List/Error Logs, 1-Click)
  - Maxtor (Legacy Seagate-compatible VSC)
  - Universal ATA (Sanitize, Security Erase, Unlock, Disable Password, Freeze Lock)
"""

import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

from core.vsc_engine import VSCEngine, detect_brand
from core.drive_detector import get_physical_drives
from core.ata_commands import ATACommandExecutor


class VSCViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.drives = []
        self.selected_drive = None
        self.vsc_engine = None
        self.detected_brand = "unknown"

        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Top Bar: Drive Selector
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="Disco Objetivo:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 4), pady=8)
        self.combo_drives = ctk.CTkComboBox(top_bar, values=["Escaneando..."], command=self._on_drive_selected, width=320)
        self.combo_drives.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

        btn_refresh = ctk.CTkButton(top_bar, text="🔄", width=36, command=self.refresh_drives)
        btn_refresh.grid(row=0, column=2, padx=(4, 10), pady=8)

        # Brand Auto-Detection Badge
        self.brand_badge = ctk.CTkLabel(
            top_bar,
            text="🏭 Marca: Detectando...",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1e293b",
            corner_radius=6,
            padx=10, pady=4
        )
        self.brand_badge.grid(row=0, column=3, padx=(4, 10), pady=8)

        # Header Info Label
        header_lbl = ctk.CTkLabel(
            self,
            text="🧪 Tratamiento de Firmware & Desbloqueo Especializado por Fabricante",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        header_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(4, 2))

        # 1-Click Universal Reset Banner
        reset_banner = ctk.CTkFrame(self, fg_color=("#1e293b", "#0f172a"), corner_radius=10, border_width=1, border_color="#334155")
        reset_banner.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 5))
        reset_banner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            reset_banner, text="⚡",
            font=ctk.CTkFont(size=28)
        ).grid(row=0, column=0, padx=(14, 6), pady=10)

        reset_info = ctk.CTkFrame(reset_banner, fg_color="transparent")
        reset_info.grid(row=0, column=1, sticky="ew", padx=4, pady=10)
        ctk.CTkLabel(
            reset_info,
            text="Reset SMART Universal de 1-Clic",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w")
        ctk.CTkLabel(
            reset_info,
            text="Detecta automáticamente la marca del disco y ejecuta la secuencia completa de reset VSC correspondiente.",
            font=ctk.CTkFont(size=10),
            text_color="gray70"
        ).pack(anchor="w")

        self.btn_1click = ctk.CTkButton(
            reset_banner,
            text="⚡ 1-CLICK FULL RESET",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#dc2626",
            hover_color="#991b1b",
            height=40,
            width=200,
            command=self._cmd_1click_reset
        )
        self.btn_1click.grid(row=0, column=2, padx=(10, 14), pady=10)

        # Brand Selector Tabs
        self.brand_tabs = ctk.CTkTabview(self)
        self.brand_tabs.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)

        tab_wd = self.brand_tabs.add("🔴 Western Digital")
        tab_sea = self.brand_tabs.add("🔵 Seagate")
        tab_sam = self.brand_tabs.add("🟣 Samsung")
        tab_tosh = self.brand_tabs.add("🟢 Toshiba")
        tab_hita = self.brand_tabs.add("🟠 Hitachi / HGST")
        tab_max = self.brand_tabs.add("⚪ Maxtor (Legacy)")
        tab_univ = self.brand_tabs.add("🌐 Universal ATA")

        self._setup_wd_tab(tab_wd)
        self._setup_seagate_tab(tab_sea)
        self._setup_samsung_tab(tab_sam)
        self._setup_toshiba_tab(tab_tosh)
        self._setup_hitachi_tab(tab_hita)
        self._setup_maxtor_tab(tab_max)
        self._setup_universal_tab(tab_univ)

    # =============================================================
    # WESTERN DIGITAL TAB
    # =============================================================
    def _setup_wd_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        # Info Card
        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🔴 Western Digital (Arquitectura Marvell / ROYL): Comandos VSC Directos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f87171").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Permite desbloquear la Service Area (SA) y resetear módulos de firmware por el cable SATA/USB:\n"
            "1. SuperOn: Habilita acceso a módulos de fábrica.\n"
            "2. Módulo 0x21: SMART | 3. Módulo 0x32: G-List | 4. Módulo 0x33: Translator | 5. Módulo 0x47: Head Map"
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # Row 1: Core Operations
        ctk.CTkLabel(scroll, text="Operaciones Principales:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fca5a5").grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkButton(scroll, text="🔓 1. SuperOn Unlock (0x80)", fg_color="#991b1b", height=34, command=self._cmd_wd_superon).grid(row=2, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 2. Reset SMART (Mod 0x21)", fg_color="#b91c1c", height=34, command=self._cmd_wd_clear_smart).grid(row=2, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 3. Limpiar G-List (Mod 0x32)", fg_color="#dc2626", height=34, command=self._cmd_wd_clear_glist).grid(row=2, column=2, padx=6, pady=4, sticky="ew")

        # Row 2: Extended Operations
        ctk.CTkLabel(scroll, text="Operaciones Extendidas:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fca5a5").grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))

        ctk.CTkButton(scroll, text="🔄 4. Regenerar Translator (Mod 0x33)", fg_color="#7f1d1d", height=34, command=self._cmd_wd_clear_translator).grid(row=4, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧠 5. Reset Head Map (Mod 0x47)", fg_color="#7f1d1d", height=34, command=self._cmd_wd_clear_headmap).grid(row=4, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="⚡ 6. Full WD Reset (1-Click)", fg_color="#450a0a", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("western_digital")).grid(row=4, column=2, padx=6, pady=4, sticky="ew")

        # Row 3: Module Backup (Read)
        ctk.CTkLabel(scroll, text="Lectura / Backup de Módulos:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fca5a5").grid(row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))

        for col, (mod_id, mod_name) in enumerate([(0x21, "SMART 0x21"), (0x32, "G-List 0x32"), (0x33, "Translator 0x33")]):
            ctk.CTkButton(scroll, text=f"📖 Leer {mod_name}", fg_color="#374151", height=30, command=lambda m=mod_id, n=mod_name: self._cmd_wd_read_module(m, n)).grid(row=6, column=col, padx=6, pady=4, sticky="ew")

    # =============================================================
    # SEAGATE TAB
    # =============================================================
    def _setup_seagate_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🔵 Seagate: Comandos VSC Directos por ATA + Terminal Serial", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Método 1 — VSC vía ATA (cable USB/SATA): Compatible con Barracuda 7200.11/12 y algunos Rosewood.\n"
            "Método 2 — Terminal Serial F3 (38400 baudios): Compatible con TODOS los Seagate con puerto diagnóstico.\n\n"
            "Si los comandos VSC fallan por el bridge USB, usa la Terminal Serial (pestaña 'Terminal Serial')."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # Row 1: VSC via ATA
        ctk.CTkLabel(scroll, text="VSC Directos vía ATA (Cable USB/SATA):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#93c5fd").grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkButton(scroll, text="🔓 Enter Diagnostic Mode", fg_color="#1e3a5f", height=34, command=self._cmd_sea_enter_diag).grid(row=2, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 Clear SMART Data", fg_color="#1e40af", height=34, command=self._cmd_sea_clear_smart).grid(row=2, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 Clear G-List", fg_color="#1d4ed8", height=34, command=self._cmd_sea_clear_glist).grid(row=2, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(scroll, text="🔄 Regenerar Translator", fg_color="#1e3a5f", height=34, command=self._cmd_sea_regen_translator).grid(row=3, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="⚠️ Clear P-List (Fábrica)", fg_color="#1e3a5f", height=34, command=self._cmd_sea_clear_plist).grid(row=3, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="⚡ Full Seagate Reset (1-Click)", fg_color="#172554", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("seagate")).grid(row=3, column=2, padx=6, pady=4, sticky="ew")

        # Row 2: Serial Terminal Reference
        ctk.CTkLabel(scroll, text="Referencia Terminal Serial (F3 a 38400 baudios):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#93c5fd").grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 2))

        serial_card = ctk.CTkFrame(scroll, fg_color=("gray85", "gray20"), corner_radius=6)
        serial_card.grid(row=5, column=0, columnspan=3, sticky="ew", padx=6, pady=4)
        serial_info = (
            "  Paso 1: [Ctrl+Z] → Despertar 'F3 T>'\n"
            "  Paso 2: /T → i4,1,22  (Limpiar G-List)\n"
            "  Paso 3: /1 → N1,,22   (Reset SMART completo)\n"
            "  Paso 4: /T → m0,6,2,,,,,22  (Regenerar Translator)\n"
            "  Paso 5: Power Cycle (Apagar y encender disco)"
        )
        ctk.CTkLabel(serial_card, text=serial_info, font=("Consolas", 10), justify="left", text_color="#a5f3fc").pack(anchor="w", padx=12, pady=8)

    # =============================================================
    # SAMSUNG TAB
    # =============================================================
    def _setup_samsung_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🟣 Samsung SpinPoint & Legacy: Comandos VSC", font=ctk.CTkFont(size=13, weight="bold"), text_color="#a855f7").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Comandos VSC directos para discos duros mecánicos Samsung (SpinPoint, HD103, HD502, HD154, HD204):\n"
            "1. Entrar a Service Area (0xDF) → Habilita acceso a módulos internos.\n"
            "2. Limpiar SMART Logs (0xE0) → Resetea contadores de atributos.\n"
            "3. Limpiar G-List (0xE4) → Borra tabla de sectores reasignados."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(scroll, text="🔓 1. Entrar a Service Area (0xDF)", fg_color="#6b21a8", height=34, command=self._cmd_sam_enter).grid(row=1, column=0, padx=6, pady=8, sticky="ew")
        ctk.CTkButton(scroll, text="📊 2. Limpiar SMART (0xE0)", fg_color="#7e22ce", height=34, command=self._cmd_sam_clear_smart).grid(row=1, column=1, padx=6, pady=8, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 3. Limpiar G-List (0xE4)", fg_color="#9333ea", height=34, command=self._cmd_sam_clear_glist).grid(row=1, column=2, padx=6, pady=8, sticky="ew")

        ctk.CTkButton(scroll, text="⚡ Full Samsung Reset (1-Click)", fg_color="#3b0764", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("samsung")).grid(row=2, column=0, columnspan=3, padx=6, pady=4, sticky="ew")

    # =============================================================
    # TOSHIBA TAB
    # =============================================================
    def _setup_toshiba_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🟢 Toshiba (MQ / DT Series): Comandos VSC Directos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34d399").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Comandos VSC directos para discos Toshiba MQ01, MQ04, DT01, DT02, MK series:\n"
            "1. Entrar a Modo de Servicio (0xFE) → Habilita comandos de diagnóstico.\n"
            "2. Limpiar SMART (0xFE/0x10) → Resetea contadores y atributos.\n"
            "3. Limpiar G-List (0xFE/0x11) → Borra tabla de defectos.\n"
            "4. Regenerar Translator (0xFE/0x20) → Reconstruye tabla LBA."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(scroll, text="🔓 1. Enter Service Mode (0xFE)", fg_color="#064e3b", height=34, command=self._cmd_tosh_enter).grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 2. Clear SMART", fg_color="#065f46", height=34, command=self._cmd_tosh_clear_smart).grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 3. Clear G-List", fg_color="#047857", height=34, command=self._cmd_tosh_clear_glist).grid(row=1, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(scroll, text="🔄 4. Regenerar Translator", fg_color="#064e3b", height=34, command=self._cmd_tosh_regen_translator).grid(row=2, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="⚡ Full Toshiba Reset (1-Click)", fg_color="#022c22", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("toshiba")).grid(row=2, column=1, columnspan=2, padx=6, pady=4, sticky="ew")

    # =============================================================
    # HITACHI / HGST TAB
    # =============================================================
    def _setup_hitachi_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🟠 Hitachi / HGST (Ultrastar / Deskstar / Travelstar): VSC Directos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#fb923c").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Comandos VSC directos para discos Hitachi, HGST, IC35 series:\n"
            "1. Entrar a Modo de Servicio (0xFC) → Habilita acceso a NV-RAM.\n"
            "2. Borrar NV-RAM SMART (0xFC/0x10) → Resetea SMART no-volátil.\n"
            "3. Limpiar G-List (0xFC/0x11) → Borra tabla de defectos.\n"
            "4. Limpiar Error Logs (0xFC/0x12) → Borra registros de errores internos."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(scroll, text="🔓 1. Enter Service Mode (0xFC)", fg_color="#7c2d12", height=34, command=self._cmd_hita_enter).grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 2. Clear NV-RAM SMART", fg_color="#9a3412", height=34, command=self._cmd_hita_clear_smart).grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 3. Clear G-List", fg_color="#c2410c", height=34, command=self._cmd_hita_clear_glist).grid(row=1, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(scroll, text="📋 4. Clear Error Logs", fg_color="#7c2d12", height=34, command=self._cmd_hita_clear_errors).grid(row=2, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="⚡ Full Hitachi Reset (1-Click)", fg_color="#431407", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("hitachi")).grid(row=2, column=1, columnspan=2, padx=6, pady=4, sticky="ew")

    # =============================================================
    # MAXTOR TAB (LEGACY)
    # =============================================================
    def _setup_maxtor_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="⚪ Maxtor (DiamondMax / MaXLine / Atlas): VSC Legacy", font=ctk.CTkFont(size=13, weight="bold"), text_color="#d1d5db").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Maxtor fue adquirido por Seagate. Los comandos VSC usan la misma familia de opcodes (0x3B).\n"
            "Compatible con DiamondMax, MaXLine, Atlas y modelos heredados."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkButton(scroll, text="🔓 Enter Diagnostic Mode", fg_color="#374151", height=34, command=self._cmd_max_enter_diag).grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 Clear SMART Data", fg_color="#4b5563", height=34, command=self._cmd_max_clear_smart).grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧹 Clear G-List", fg_color="#6b7280", height=34, command=self._cmd_max_clear_glist).grid(row=1, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(scroll, text="⚡ Full Maxtor Reset (1-Click)", fg_color="#1f2937", height=34, font=ctk.CTkFont(weight="bold"), command=lambda: self._cmd_brand_full_reset("maxtor")).grid(row=2, column=0, columnspan=3, padx=6, pady=4, sticky="ew")

    # =============================================================
    # UNIVERSAL ATA TAB
    # =============================================================
    def _setup_universal_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🌐 Universal ATA: Sanitize, Security Erase & Password Management", font=ctk.CTkFont(size=13, weight="bold"), text_color="#fbbf24").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Compatible con discos duros y SSDs de CUALQUIER fabricante:\n"
            "• ATA Sanitize: Crypto Scramble / Overwrite — destruye tablas criptográficas.\n"
            "• Enhanced Security Erase: Reevalúa sectores y purga falsos defectuosos.\n"
            "• Security Unlock / Disable Password: Gestión de contraseñas ATA.\n"
            "• Freeze Lock: Bloquea cambios de seguridad hasta siguiente power cycle."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        # Row 1: Sanitize
        ctk.CTkLabel(scroll, text="ATA Sanitize Device:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fde68a").grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2))

        ctk.CTkButton(scroll, text="🔐 Crypto Scramble", fg_color="#854d0e", height=34, command=lambda: self._cmd_sanitize("crypto")).grid(row=2, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📝 Overwrite", fg_color="#92400e", height=34, command=lambda: self._cmd_sanitize("overwrite")).grid(row=2, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="📊 Check Sanitize Status", fg_color="#78350f", height=34, command=self._cmd_sanitize_status).grid(row=2, column=2, padx=6, pady=4, sticky="ew")

        # Row 2: Security
        ctk.CTkLabel(scroll, text="ATA Security (Password & Erase):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#fde68a").grid(row=3, column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))

        ctk.CTkButton(scroll, text="🔑 Set Password", fg_color="#a16207", height=34, command=self._cmd_sec_setpass).grid(row=4, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="💣 Enhanced Security Erase (0xF4)", fg_color="#ca8a04", height=34, command=self._cmd_sec_erase).grid(row=4, column=1, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🔓 Security Unlock (0xF2)", fg_color="#a16207", height=34, command=self._cmd_sec_unlock).grid(row=4, column=2, padx=6, pady=4, sticky="ew")

        ctk.CTkButton(scroll, text="❌ Disable Password (0xF6)", fg_color="#78350f", height=34, command=self._cmd_sec_disable_pass).grid(row=5, column=0, padx=6, pady=4, sticky="ew")
        ctk.CTkButton(scroll, text="🧊 Freeze Lock (0xF5)", fg_color="#78350f", height=34, command=self._cmd_sec_freeze).grid(row=5, column=1, padx=6, pady=4, sticky="ew")

    # =============================================================
    # DRIVE MANAGEMENT
    # =============================================================
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
            self.vsc_engine = VSCEngine(drive_path)
            
            # Auto-detect brand
            model = self.selected_drive.get("model", "")
            self.detected_brand = detect_brand(model)
            self._update_brand_badge()
            self._auto_switch_tab()
            self._log(f"VSC Engine enlazado a: {drive_path} | Marca detectada: {self.detected_brand.upper()}")

    def _update_brand_badge(self):
        brand_display = {
            "western_digital": ("🔴 Western Digital", "#dc2626"),
            "seagate": ("🔵 Seagate", "#2563eb"),
            "samsung": ("🟣 Samsung", "#7c3aed"),
            "toshiba": ("🟢 Toshiba", "#059669"),
            "hitachi": ("🟠 Hitachi / HGST", "#ea580c"),
            "maxtor": ("⚪ Maxtor (Legacy)", "#6b7280"),
            "unknown": ("❓ Marca Desconocida", "#4b5563"),
        }
        text, color = brand_display.get(self.detected_brand, ("❓ Desconocido", "#4b5563"))
        self.brand_badge.configure(text=f"🏭 {text}", fg_color=color)

    def _auto_switch_tab(self):
        """Automatically switches to the correct brand tab when a drive is selected."""
        tab_mapping = {
            "western_digital": "🔴 Western Digital",
            "seagate": "🔵 Seagate",
            "samsung": "🟣 Samsung",
            "toshiba": "🟢 Toshiba",
            "hitachi": "🟠 Hitachi / HGST",
            "maxtor": "⚪ Maxtor (Legacy)",
        }
        tab_name = tab_mapping.get(self.detected_brand)
        if tab_name:
            try:
                self.brand_tabs.set(tab_name)
            except Exception:
                pass

    # =============================================================
    # 1-CLICK UNIVERSAL RESET
    # =============================================================
    def _cmd_1click_reset(self):
        if not self.vsc_engine:
            return
        if self.detected_brand == "unknown":
            messagebox.showwarning(
                "Marca No Detectada",
                "No se pudo detectar automáticamente la marca del disco.\n"
                "Selecciona manualmente la pestaña de la marca correcta y usa los botones individuales."
            )
            return
        
        brand_names = {
            "western_digital": "Western Digital",
            "seagate": "Seagate",
            "samsung": "Samsung",
            "toshiba": "Toshiba",
            "hitachi": "Hitachi / HGST",
            "maxtor": "Maxtor",
        }
        brand_name = brand_names.get(self.detected_brand, self.detected_brand)
        
        msg = (
            f"⚡ RESET SMART UNIVERSAL DE 1-CLIC\n\n"
            f"Marca detectada: {brand_name}\n"
            f"Disco: {self.selected_drive.get('model')}\n"
            f"Path: {self.selected_drive.get('path')}\n\n"
            f"Se ejecutará la secuencia completa de Reset SMART + G-List para {brand_name}.\n\n"
            f"IMPORTANTE: Después del reset, debes realizar un Power Cycle\n"
            f"(apagar y encender el disco) para que los cambios surtan efecto.\n\n"
            f"¿Continuar?"
        )
        if not messagebox.askyesno("Confirmar 1-Click Reset", msg, icon="warning"):
            return

        self._cmd_brand_full_reset(self.detected_brand)

    def _cmd_brand_full_reset(self, brand: str):
        if not self.vsc_engine:
            return
        def worker():
            brand_upper = brand.upper().replace("_", " ")
            self._log(f"⚡ Iniciando secuencia FULL RESET para {brand_upper}...")
            try:
                results = self.vsc_engine.execute_full_reset_by_brand(brand)
                success_count = 0
                fail_count = 0
                for step_info in results:
                    step = step_info.get("step", "?")
                    res = step_info.get("result", {})
                    ok = res.get("success", False)
                    if ok:
                        success_count += 1
                    else:
                        fail_count += 1
                    self._log(f"  [{brand_upper}] {step}: {'✅ OK' if ok else '❌ FAIL'} (SCSI={res.get('scsi_status', '?')})")
                    if not ok:
                        hint = res.get("error_hint")
                        if hint:
                            self._log(f"    └─ ⚠️ {hint}")

                self._log(f"⚡ RESULTADO FINAL {brand_upper}: {success_count} exitosos, {fail_count} fallidos de {len(results)} pasos.")
                self._log(f"⚠️ RECORDATORIO: Desconecta y reconecta el disco (Power Cycle) para aplicar los cambios.")
            except Exception as e:
                self._log(f"❌ Excepción durante Full Reset {brand_upper}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    # =============================================================
    # WD COMMAND HANDLERS
    # =============================================================
    def _cmd_wd_superon(self):
        self._run_vsc_cmd("WD SuperOn Unlock (0x80)", lambda: self.vsc_engine.wd_superon_unlock())

    def _cmd_wd_clear_smart(self):
        self._run_vsc_cmd("WD Clear SMART Module (0x21)", lambda: self.vsc_engine.wd_clear_smart_module())

    def _cmd_wd_clear_glist(self):
        self._run_vsc_cmd("WD Clear G-List Module (0x32)", lambda: self.vsc_engine.wd_clear_glist_module())

    def _cmd_wd_clear_translator(self):
        self._run_vsc_cmd("WD Clear Translator Module (0x33)", lambda: self.vsc_engine.wd_clear_translator_module())

    def _cmd_wd_clear_headmap(self):
        if not messagebox.askyesno("Confirmar", "⚠️ Limpiar el Head Map (Mod 0x47) solo es seguro si todos los cabezales están físicamente funcionales.\n\n¿Continuar?"):
            return
        self._run_vsc_cmd("WD Clear Head Map Module (0x47)", lambda: self.vsc_engine.wd_clear_head_map_module())

    def _cmd_wd_read_module(self, mod_id, mod_name):
        if not self.vsc_engine:
            return
        def worker():
            self._log(f"Leyendo módulo WD {mod_name}...")
            try:
                res = self.vsc_engine.wd_read_module(module_id=mod_id)
                if res.get("success") and res.get("data"):
                    data = res["data"]
                    # Offer to save backup
                    save_path = filedialog.asksaveasfilename(
                        title=f"Guardar Backup del Módulo {mod_name}",
                        defaultextension=".bin",
                        filetypes=[("Archivo Binario", "*.bin"), ("Todos", "*.*")],
                        initialfile=f"WD_Module_{mod_name.replace(' ', '_')}_backup.bin"
                    )
                    if save_path:
                        with open(save_path, "wb") as f:
                            f.write(data)
                        self._log(f"✅ Backup del módulo {mod_name} guardado: {save_path}")
                    else:
                        self._log(f"Módulo {mod_name} leído ({len(data)} bytes), backup cancelado.")
                else:
                    self._log(f"❌ Error leyendo módulo {mod_name}: SCSI={res.get('scsi_status')}")
            except Exception as e:
                self._log(f"❌ Excepción leyendo módulo {mod_name}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    # =============================================================
    # SEAGATE COMMAND HANDLERS
    # =============================================================
    def _cmd_sea_enter_diag(self):
        self._run_vsc_cmd("Seagate Enter Diagnostic Mode", lambda: self.vsc_engine.seagate_vsc_enter_diagnostic())

    def _cmd_sea_clear_smart(self):
        self._run_vsc_cmd("Seagate Clear SMART Data", lambda: self.vsc_engine.seagate_vsc_clear_smart())

    def _cmd_sea_clear_glist(self):
        self._run_vsc_cmd("Seagate Clear G-List", lambda: self.vsc_engine.seagate_vsc_clear_glist())

    def _cmd_sea_clear_plist(self):
        if not messagebox.askyesno("⚠️ Confirmar", "Limpiar la P-List (Primary/Factory Defect List) elimina marcas de defectos de fábrica.\nEsto rara vez es necesario y puede causar problemas.\n\n¿Estás seguro?"):
            return
        self._run_vsc_cmd("Seagate Clear P-List", lambda: self.vsc_engine.seagate_vsc_clear_plist())

    def _cmd_sea_regen_translator(self):
        self._run_vsc_cmd("Seagate Regenerate Translator", lambda: self.vsc_engine.seagate_vsc_regenerate_translator())

    # =============================================================
    # SAMSUNG COMMAND HANDLERS
    # =============================================================
    def _cmd_sam_enter(self):
        self._run_vsc_cmd("Samsung Enter Service Area (0xDF)", lambda: self.vsc_engine.samsung_vsc_enter_sa())

    def _cmd_sam_clear_smart(self):
        self._run_vsc_cmd("Samsung Clear SMART Logs (0xE0)", lambda: self.vsc_engine.samsung_vsc_clear_smart())

    def _cmd_sam_clear_glist(self):
        self._run_vsc_cmd("Samsung Clear G-List (0xE4)", lambda: self.vsc_engine.samsung_vsc_clear_glist())

    # =============================================================
    # TOSHIBA COMMAND HANDLERS
    # =============================================================
    def _cmd_tosh_enter(self):
        self._run_vsc_cmd("Toshiba Enter Service Mode (0xFE)", lambda: self.vsc_engine.toshiba_vsc_enter_service_mode())

    def _cmd_tosh_clear_smart(self):
        self._run_vsc_cmd("Toshiba Clear SMART", lambda: self.vsc_engine.toshiba_vsc_clear_smart())

    def _cmd_tosh_clear_glist(self):
        self._run_vsc_cmd("Toshiba Clear G-List", lambda: self.vsc_engine.toshiba_vsc_clear_glist())

    def _cmd_tosh_regen_translator(self):
        self._run_vsc_cmd("Toshiba Regenerate Translator", lambda: self.vsc_engine.toshiba_vsc_regenerate_translator())

    # =============================================================
    # HITACHI COMMAND HANDLERS
    # =============================================================
    def _cmd_hita_enter(self):
        self._run_vsc_cmd("Hitachi Enter Service Mode (0xFC)", lambda: self.vsc_engine.hitachi_vsc_enter_service_mode())

    def _cmd_hita_clear_smart(self):
        self._run_vsc_cmd("Hitachi Clear NV-RAM SMART", lambda: self.vsc_engine.hitachi_vsc_clear_smart_nvram())

    def _cmd_hita_clear_glist(self):
        self._run_vsc_cmd("Hitachi Clear G-List", lambda: self.vsc_engine.hitachi_vsc_clear_glist())

    def _cmd_hita_clear_errors(self):
        self._run_vsc_cmd("Hitachi Clear Error Logs", lambda: self.vsc_engine.hitachi_vsc_clear_error_logs())

    # =============================================================
    # MAXTOR COMMAND HANDLERS
    # =============================================================
    def _cmd_max_enter_diag(self):
        self._run_vsc_cmd("Maxtor Enter Diagnostic Mode", lambda: self.vsc_engine.maxtor_vsc_enter_diagnostic())

    def _cmd_max_clear_smart(self):
        self._run_vsc_cmd("Maxtor Clear SMART Data", lambda: self.vsc_engine.maxtor_vsc_clear_smart())

    def _cmd_max_clear_glist(self):
        self._run_vsc_cmd("Maxtor Clear G-List", lambda: self.vsc_engine.maxtor_vsc_clear_glist())

    # =============================================================
    # UNIVERSAL ATA COMMAND HANDLERS
    # =============================================================
    def _cmd_sanitize(self, mode: str):
        self._run_vsc_cmd(f"ATA Sanitize ({mode})", lambda: self.vsc_engine.ata_sanitize_device(mode))

    def _cmd_sanitize_status(self):
        self._run_vsc_cmd("ATA Sanitize Status", lambda: self.vsc_engine.ata_sanitize_status())

    def _cmd_sec_setpass(self):
        self._run_vsc_cmd("ATA Security Set Password", lambda: self.vsc_engine.ata_security_set_password("Terminator123"))

    def _cmd_sec_erase(self):
        if not messagebox.askyesno("Confirmar Borrado de Seguridad", "Enhanced Security Erase sobreescribirá todos los sectores y reevaluará los sectores defectuosos.\n¿Deseas continuar?"):
            return
        self._run_vsc_cmd("ATA Enhanced Security Erase", lambda: self.vsc_engine.ata_security_erase(enhanced=True))

    def _cmd_sec_unlock(self):
        self._run_vsc_cmd("ATA Security Unlock (0xF2)", lambda: self.vsc_engine.ata_security_unlock("Terminator123"))

    def _cmd_sec_disable_pass(self):
        self._run_vsc_cmd("ATA Security Disable Password (0xF6)", lambda: self.vsc_engine.ata_security_disable_password("Terminator123"))

    def _cmd_sec_freeze(self):
        self._run_vsc_cmd("ATA Security Freeze Lock (0xF5)", lambda: self.vsc_engine.ata_security_freeze_lock())

    # =============================================================
    # HELPERS
    # =============================================================
    def _run_vsc_cmd(self, cmd_name: str, func):
        """Generic helper to run any VSC command in a thread with logging."""
        if not self.vsc_engine:
            return
        def worker():
            self._log(f"Ejecutando: {cmd_name}...")
            try:
                res = func()
                ok = res.get("success", False)
                extra = ""
                if not ok:
                    sense = f"Sense=Key:{res.get('sense_key', '?')} ASC:{res.get('asc', '?')} ASCQ:{res.get('ascq', '?')}" if res.get("sense_data") else "Sense: (sin datos)"
                    extra = f" | {sense}"
                    hint = res.get("error_hint")
                    if hint:
                        extra += f" | {hint}"
                self._log(f"{cmd_name}: {'✅ OK' if ok else '❌ FAIL'} | SCSI={res.get('scsi_status', '?')} | Win32={res.get('win32_error', '?')}{extra}")
            except Exception as e:
                self._log(f"❌ Excepción en {cmd_name}: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[VSC-LAB] {text}")
