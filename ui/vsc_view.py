"""
Vendor Specific Commands & Brand-Specific Laboratory View
Clearly organized by manufacturer: Seagate, Western Digital, Toshiba/Hitachi, Samsung, and Universal ATA.
"""

import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from core.vsc_engine import VSCEngine
from core.drive_detector import get_physical_drives

class VSCViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.drives = []
        self.selected_drive = None
        self.vsc_engine = None

        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Top Bar: Drive Selector
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="Disco Objetivo:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 4), pady=8)
        self.combo_drives = ctk.CTkComboBox(top_bar, values=["Escaneando..."], command=self._on_drive_selected, width=320)
        self.combo_drives.grid(row=0, column=1, padx=4, pady=8, sticky="ew")

        btn_refresh = ctk.CTkButton(top_bar, text="🔄", width=36, command=self.refresh_drives)
        btn_refresh.grid(row=0, column=2, padx=(4, 10), pady=8)

        # Header Info Label
        header_lbl = ctk.CTkLabel(
            self,
            text="🧪 Tratamiento de Firmware & Desbloqueo Especializado por Fabricante",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        header_lbl.grid(row=1, column=0, sticky="w", padx=14, pady=(4, 2))

        # Brand Selector Tabs
        self.brand_tabs = ctk.CTkTabview(self)
        self.brand_tabs.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        tab_sea = self.brand_tabs.add("🔵 Seagate (F3)")
        tab_wd = self.brand_tabs.add("🔴 Western Digital")
        tab_tosh = self.brand_tabs.add("🟢 Toshiba / Hitachi")
        tab_sam = self.brand_tabs.add("🟣 Samsung")
        tab_univ = self.brand_tabs.add("🌐 Universal ATA")

        self._setup_seagate_tab(tab_sea)
        self._setup_wd_tab(tab_wd)
        self._setup_toshiba_tab(tab_tosh)
        self._setup_samsung_tab(tab_sam)
        self._setup_universal_tab(tab_univ)

    def _setup_seagate_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🔵 Seagate F3: Protocolo de Reparación & Limpieza", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Para discos Seagate (Barracuda, 7200.11, 7200.12, Rosewood, etc.):\n"
            "Los comandos se ejecutan a través de la Terminal Serial (Pestaña 'Terminal Serial') a 38400 baudios:\n\n"
            "• Paso 1: Presiona [Ctrl+Z] para despertar el prompt 'F3 T>'\n"
            "• Paso 2: Limpiar G-List de sectores reasignados: 'i4,1,22'\n"
            "• Paso 3: Resetear atributos y contadores SMART a 0: '/1' -> 'N1,,22'\n"
            "• Paso 4: Reconstruir tabla de traducción LBA / Formateo de partición: '/T' -> 'm0,6,2,,,,,22'\n"
            "• Paso 5: Apagar y encender el disco (Power Cycle)."
        )
        ctk.CTkLabel(card, text=info, font=("Consolas", 10), justify="left", text_color="#e2e8f0").pack(anchor="w", padx=12, pady=(0, 12))

    def _setup_wd_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🔴 Western Digital (Arquitectura Marvel / ROYL): Comandos VSC Directos", font=ctk.CTkFont(size=13, weight="bold"), text_color="#f87171").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Permite desbloquear la Service Area (SA) y resetear módulos de firmware por el cable SATA/USB:\n"
            "1. Desbloqueo SuperOn: Habilita el acceso a los módulos de fábrica.\n"
            "2. Módulo 0x21: Almacena la tabla y contadores SMART (Se sobreescribe con ceros).\n"
            "3. Módulo 0x32: Almacena la lista G de sectores reasignados."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        btn_superon = ctk.CTkButton(scroll, text="1. Desbloquear SuperOn (0x80)", fg_color="#991b1b", height=34, command=self._cmd_wd_superon)
        btn_superon.grid(row=1, column=0, padx=6, pady=8, sticky="ew")

        btn_smart = ctk.CTkButton(scroll, text="2. Reset SMART (Mod 0x21)", fg_color="#b91c1c", height=34, command=self._cmd_wd_clear_smart)
        btn_smart.grid(row=1, column=1, padx=6, pady=8, sticky="ew")

        btn_glist = ctk.CTkButton(scroll, text="3. Limpiar G-List (Mod 0x32)", fg_color="#dc2626", height=34, command=self._cmd_wd_clear_glist)
        btn_glist.grid(row=1, column=2, padx=6, pady=8, sticky="ew")

    def _setup_toshiba_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.pack(fill="x", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🟢 Toshiba & Hitachi / HGST: Procedimiento de Diagnóstico", font=ctk.CTkFont(size=13, weight="bold"), text_color="#34d399").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "• Toshiba (Series MQ / DT):\n"
            "  1. Conectar por Terminal Serial (9600 o 115200 baudios).\n"
            "  2. Presionar Enter repetidamente para despertar la consola.\n"
            "  3. Ejecutar comando '/ -> M0' para realizar formateo a bajo nivel y reconstruir listas de defectos P/G.\n\n"
            "• Hitachi / HGST (Ultrastar / Deskstar):\n"
            "  1. Soportan borrado criptográfico directo mediante ATA Sanitize (Pestaña 'Universal ATA').\n"
            "  2. VSC directos para borrado de NV-RAM."
        )
        ctk.CTkLabel(card, text=info, font=("Consolas", 10), justify="left", text_color="#e2e8f0").pack(anchor="w", padx=12, pady=(0, 12))

    def _setup_samsung_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🟣 Samsung SpinPoint & Legacy: Comandos VSC", font=ctk.CTkFont(size=13, weight="bold"), text_color="#a855f7").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Comandos VSC directos para discos duros mecánicos Samsung:\n"
            "1. Entrar a Service Area (0xDF).\n"
            "2. Limpiar logs y restablecer defectos (0xE0 / 0xE4)."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        btn_enter = ctk.CTkButton(scroll, text="1. Entrar a Service Area (0xDF)", fg_color="#6b21a8", height=34, command=self._cmd_sam_enter)
        btn_enter.grid(row=1, column=0, padx=6, pady=8, sticky="ew")

        btn_clear = ctk.CTkButton(scroll, text="2. Limpiar SMART & Defectos (0xE0)", fg_color="#7e22ce", height=34, command=self._cmd_sam_clear)
        btn_clear.grid(row=1, column=1, padx=6, pady=8, sticky="ew")

    def _setup_universal_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2), weight=1)

        card = ctk.CTkFrame(scroll, fg_color=("gray90", "gray14"), corner_radius=8, border_width=1, border_color="#1e293b")
        card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=6, padx=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="🌐 Universal ATA: Sanitize & Enhanced Security Erase", font=ctk.CTkFont(size=13, weight="bold"), text_color="#fbbf24").pack(anchor="w", padx=12, pady=(10, 4))
        
        info = (
            "Compatible con discos duros y SSDs de CUALQUIER fabricante (Seagate, WD, Kingston, Crucial, SanDisk, Toshiba, etc.):\n"
            "• Enhanced Security Erase: Obliga al microcódigo interno a reevaluar sectores y purgar candidatos defectuosos falsos.\n"
            "• ATA Sanitize: Destruye las tablas criptográficas y reinicia contadores de error."
        )
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=11), text_color="gray70", justify="left").pack(anchor="w", padx=12, pady=(0, 10))

        btn_crypto = ctk.CTkButton(scroll, text="ATA Sanitize: Crypto Scramble", fg_color="#854d0e", height=34, command=lambda: self._cmd_sanitize("crypto"))
        btn_crypto.grid(row=1, column=0, padx=6, pady=8, sticky="ew")

        btn_pass = ctk.CTkButton(scroll, text="Set Master Password", fg_color="#a16207", height=34, command=self._cmd_sec_setpass)
        btn_pass.grid(row=1, column=1, padx=6, pady=8, sticky="ew")

        btn_erase = ctk.CTkButton(scroll, text="Enhanced Security Erase (0xF4)", fg_color="#ca8a04", height=34, command=self._cmd_sec_erase)
        btn_erase.grid(row=1, column=2, padx=6, pady=8, sticky="ew")

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
            self._log(f"VSC Engine enlazado a: {drive_path}")

    def _cmd_wd_superon(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Enviando secuencia ATA VSC SuperOn a Western Digital...")
            try:
                res = self.vsc_engine.wd_superon_unlock()
                self._log(f"SuperOn enviado: Éxito={res.get('success')} | SCSI Status={res.get('scsi_status')}")
            except Exception as e:
                self._log(f"Excepción en SuperOn: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_wd_clear_smart(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Sobreescribiendo Módulo 0x21 (SMART) con ceros vía VSC Write Module...")
            try:
                res = self.vsc_engine.wd_clear_smart_module()
                self._log(f"Módulo 0x21 procesado: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción limpiando Módulo 0x21: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_wd_clear_glist(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Sobreescribiendo Módulo 0x32 (G-List Defect Table) con ceros...")
            try:
                res = self.vsc_engine.wd_clear_glist_module()
                self._log(f"Módulo 0x32 procesado: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción limpiando Módulo 0x32: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_sam_enter(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Enviando VSC Samsung Enter Service Area (0xDF)...")
            try:
                res = self.vsc_engine.samsung_vsc_enter_sa()
                self._log(f"Samsung SA: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción Samsung SA: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_sam_clear(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Enviando VSC Samsung Clear SMART Logs (0xE0)...")
            try:
                res = self.vsc_engine.samsung_vsc_clear_smart()
                self._log(f"Samsung Clear: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción Samsung Clear: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_sanitize(self, mode: str):
        if not self.vsc_engine:
            return
        def worker():
            self._log(f"Enviando ATA Sanitize Device ({mode})...")
            try:
                res = self.vsc_engine.ata_sanitize_device(mode)
                self._log(f"Sanitize {mode}: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción en Sanitize: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_sec_setpass(self):
        if not self.vsc_engine:
            return
        def worker():
            self._log("Estableciendo contraseña de seguridad ATA temporal (Terminator123)...")
            try:
                res = self.vsc_engine.ata_security_set_password("Terminator123")
                self._log(f"Password establecido: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción en Security Set Password: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_sec_erase(self):
        if not self.vsc_engine:
            return
        if not messagebox.askyesno("Confirmar Borrado de Seguridad", "Enhanced Security Erase sobreescribirá todos los sectores y reevaluará los sectores defectuosos.\n¿Deseas continuar?"):
            return
        def worker():
            self._log("Iniciando ATA Enhanced Security Erase...")
            try:
                res = self.vsc_engine.ata_security_erase(enhanced=True, password="Terminator123")
                self._log(f"Enhanced Erase iniciado: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción en Enhanced Erase: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[VSC-LAB] {text}")

