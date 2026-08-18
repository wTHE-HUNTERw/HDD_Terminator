"""
ATA Direct Command & SMART Diagnostic View
Provides GUI controls for executing ATA commands via USB SPTI Pass-Through.
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk

from core.drive_detector import get_physical_drives
from core.ata_commands import ATACommandExecutor
from ui.hex_view import HexViewFrame

class ATAViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.drives = []
        self.selected_drive = None
        self.executor = None

        self._setup_ui()
        self.refresh_drives()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Top Bar: Drive Selection & Refresh
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        drive_label = ctk.CTkLabel(top_bar, text="Dispositivo Físico:", font=ctk.CTkFont(size=13, weight="bold"))
        drive_label.grid(row=0, column=0, padx=(10, 5), pady=10)

        self.drive_combo = ctk.CTkComboBox(
            top_bar,
            values=["Escaneando..."],
            command=self._on_drive_selected,
            width=350
        )
        self.drive_combo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.btn_refresh = ctk.CTkButton(
            top_bar,
            text="🔄 Actualizar Discos",
            width=140,
            command=self.refresh_drives
        )
        self.btn_refresh.grid(row=0, column=2, padx=(5, 10), pady=10)

        # Device Info Summary Card
        self.info_card = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=8)
        self.info_card.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        self.info_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.lbl_model = ctk.CTkLabel(self.info_card, text="Modelo: -", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_model.grid(row=0, column=0, padx=10, pady=6, sticky="w")

        self.lbl_serial = ctk.CTkLabel(self.info_card, text="Serial: -", font=ctk.CTkFont(size=12))
        self.lbl_serial.grid(row=0, column=1, padx=10, pady=6, sticky="w")

        self.lbl_firmware = ctk.CTkLabel(self.info_card, text="Firmware: -", font=ctk.CTkFont(size=12))
        self.lbl_firmware.grid(row=0, column=2, padx=10, pady=6, sticky="w")

        self.lbl_capacity = ctk.CTkLabel(self.info_card, text="Capacidad: -", font=ctk.CTkFont(size=12))
        self.lbl_capacity.grid(row=0, column=3, padx=10, pady=6, sticky="w")

        # Tabview for ATA Sub-tools
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)

        tab_smart = self.tabview.add("📊 Diagnóstico SMART & Salud")
        tab_smart_ops = self.tabview.add("🛠️ Restablecer SMART & G-List")
        tab_raw = self.tabview.add("⚡ Comandos ATA Raw / USB Pass-Through")
        tab_lba = self.tabview.add("🔍 Lector de Sectores LBA")

        self._setup_smart_tab(tab_smart)
        self._setup_smart_ops_tab(tab_smart_ops)
        self._setup_raw_tab(tab_raw)
        self._setup_lba_tab(tab_lba)

    def _setup_smart_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # Action Buttons Row 1
        btn_frame1 = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame1.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        self.btn_identify = ctk.CTkButton(
            btn_frame1,
            text="🔍 ATA IDENTIFY (0xEC)",
            fg_color="#1f538d",
            command=self._cmd_identify
        )
        self.btn_identify.pack(side="left", padx=4)

        self.btn_smart_read = ctk.CTkButton(
            btn_frame1,
            text="📋 Leer Atributos SMART",
            fg_color="#2b7a4b",
            command=self._cmd_read_smart
        )
        self.btn_smart_read.pack(side="left", padx=4)

        self.btn_smart_status = ctk.CTkButton(
            btn_frame1,
            text="🩺 Estado de Salud SMART",
            fg_color="#8c5b1e",
            command=self._cmd_smart_status
        )
        self.btn_smart_status.pack(side="left", padx=4)

        self.lbl_health_badge = ctk.CTkLabel(
            btn_frame1,
            text="Estado: Esperando lectura",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.lbl_health_badge.pack(side="right", padx=10)

        # Action Buttons Row 2: Standard ATA SMART Subcommands
        btn_frame2 = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame2.grid(row=1, column=0, sticky="ew", padx=5, pady=(2, 5))

        btn_enable_smart = ctk.CTkButton(
            btn_frame2,
            text="🟢 Habilitar SMART (0xD8)",
            width=150,
            fg_color="#166534",
            command=lambda: self._cmd_smart_toggle(True)
        )
        btn_enable_smart.pack(side="left", padx=4)

        btn_disable_smart = ctk.CTkButton(
            btn_frame2,
            text="🔴 Deshabilitar SMART (0xD9)",
            width=150,
            fg_color="#991b1b",
            command=lambda: self._cmd_smart_toggle(False)
        )
        btn_disable_smart.pack(side="left", padx=4)

        btn_short_test = ctk.CTkButton(
            btn_frame2,
            text="⚡ Self-Test Corto (0xD4)",
            width=140,
            fg_color="#4338ca",
            command=lambda: self._cmd_run_selftest("short")
        )
        btn_short_test.pack(side="left", padx=4)

        btn_ext_test = ctk.CTkButton(
            btn_frame2,
            text="🔬 Self-Test Extendido",
            width=140,
            fg_color="#3730a3",
            command=lambda: self._cmd_run_selftest("extended")
        )
        btn_ext_test.pack(side="left", padx=4)

        btn_abort_test = ctk.CTkButton(
            btn_frame2,
            text="⏹️ Cancelar Test",
            width=100,
            fg_color="#4b5563",
            command=lambda: self._cmd_run_selftest("abort")
        )
        btn_abort_test.pack(side="left", padx=4)

        # Treeview for SMART attributes
        tree_frame = ctk.CTkFrame(tab)
        tree_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background="#1e1e1e",
            foreground="#dcdcdc",
            fieldbackground="#1e1e1e",
            rowheight=24,
            font=("Segoe UI", 10)
        )
        style.configure("Treeview.Heading", background="#2d2d2d", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", "#0e639c")])

        columns = ("id", "name", "current", "worst", "raw", "health")
        self.smart_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.smart_tree.heading("id", text="ID")
        self.smart_tree.heading("name", text="Nombre del Atributo")
        self.smart_tree.heading("current", text="Valor Actual")
        self.smart_tree.heading("worst", text="Peor Valor")
        self.smart_tree.heading("raw", text="Valor Raw")
        self.smart_tree.heading("health", text="Nivel de Riesgo")

        self.smart_tree.column("id", width=50, anchor="center")
        self.smart_tree.column("name", width=250, anchor="w")
        self.smart_tree.column("current", width=90, anchor="center")
        self.smart_tree.column("worst", width=90, anchor="center")
        self.smart_tree.column("raw", width=180, anchor="center")
        self.smart_tree.column("health", width=120, anchor="center")

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.smart_tree.yview)
        self.smart_tree.configure(yscrollcommand=scroll.set)

        self.smart_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

    def _setup_raw_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Command presets & custom registers
        left_panel = ctk.CTkFrame(tab, fg_color=("gray90", "gray14"))
        left_panel.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=5, pady=5)
        left_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(left_panel, text="Parámetros de Registros ATA", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=2, pady=8)

        # Quick command presets
        ctk.CTkLabel(left_panel, text="Plantilla Rápida:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.combo_presets = ctk.CTkComboBox(
            left_panel,
            values=[
                "IDENTIFY DEVICE (0xEC)",
                "SMART READ DATA (0xB0 / 0xD0)",
                "SMART RETURN STATUS (0xB0 / 0xDA)",
                "CHECK POWER MODE (0xE5)",
                "STANDBY IMMEDIATE (0xE0)",
                "IDLE IMMEDIATE (0xE1)",
                "READ SECTORS (0x20)",
                "READ NATIVE MAX LBA (0xF8)"
            ],
            command=self._on_preset_selected
        )
        self.combo_presets.grid(row=1, column=1, sticky="ew", padx=10, pady=4)

        # Registers
        regs = [
            ("Command (Hex):", "txt_reg_cmd", "EC"),
            ("Features (Hex):", "txt_reg_feat", "00"),
            ("Sector Count (Dec):", "txt_reg_sc", "1"),
            ("LBA (Dec/Hex):", "txt_reg_lba", "0"),
            ("Device/Head (Hex):", "txt_reg_dev", "00"),
            ("Buffer Size (Bytes):", "txt_reg_buf", "512"),
            ("Dirección de Datos:", "combo_reg_dir", "in")
        ]

        self.reg_entries = {}
        for idx, (label_txt, key, default_val) in enumerate(regs, start=2):
            ctk.CTkLabel(left_panel, text=label_txt).grid(row=idx, column=0, sticky="w", padx=10, pady=3)
            if key == "combo_reg_dir":
                entry = ctk.CTkOptionMenu(left_panel, values=["in", "out", "none"])
                entry.set(default_val)
            else:
                entry = ctk.CTkEntry(left_panel)
                entry.insert(0, default_val)
            entry.grid(row=idx, column=1, sticky="ew", padx=10, pady=3)
            self.reg_entries[key] = entry

        self.chk_lba48 = ctk.CTkCheckBox(left_panel, text="Modo LBA48 Extendido")
        self.chk_lba48.grid(row=9, column=0, columnspan=2, padx=10, pady=8)

        btn_send_raw = ctk.CTkButton(
            left_panel,
            text="🚀 Ejecutar Comando ATA vía SAT",
            fg_color="#a83232",
            hover_color="#802424",
            command=self._cmd_execute_raw
        )
        btn_send_raw.grid(row=10, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Right Panel: Output Registers & Hex View
        right_panel = ctk.CTkFrame(tab, fg_color="transparent")
        right_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=5, pady=5)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)

        # Status Return Registers Box
        self.lbl_raw_return = ctk.CTkLabel(
            right_panel,
            text="Registros devueltos: Status=-- Error=-- LBA=-- Dev=--",
            font=("Consolas", 11),
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            height=28
        )
        self.lbl_raw_return.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        self.raw_hex_view = HexViewFrame(right_panel)
        self.raw_hex_view.grid(row=1, column=0, sticky="nsew")

    def _setup_lba_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top_lba = ctk.CTkFrame(tab, fg_color="transparent")
        top_lba.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        ctk.CTkLabel(top_lba, text="Sector LBA:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=5)
        self.txt_lba_target = ctk.CTkEntry(top_lba, width=150)
        self.txt_lba_target.insert(0, "0")
        self.txt_lba_target.pack(side="left", padx=5)

        btn_read_lba = ctk.CTkButton(
            top_lba,
            text="📖 Leer Sector LBA (512B)",
            command=self._cmd_read_lba
        )
        btn_read_lba.pack(side="left", padx=10)

        self.lba_hex_view = HexViewFrame(tab)
        self.lba_hex_view.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

    def refresh_drives(self):
        self.drives = get_physical_drives()
        combo_values = []
        for d in self.drives:
            usb_tag = "[USB] " if d.get("is_usb") else ""
            letters_tag = f"({d.get('letters')})" if d.get("letters") else ""
            combo_values.append(f"{usb_tag}{d.get('path')} - {d.get('model')} - {d.get('size_str')} {letters_tag}")
        
        if not combo_values:
            combo_values = ["No se detectaron discos físicos"]

        self.drive_combo.configure(values=combo_values)
        self.drive_combo.set(combo_values[0])
        self._on_drive_selected(combo_values[0])

    def _on_drive_selected(self, choice):
        if not self.drives:
            return
        selected_index = self.drive_combo.cget("values").index(choice) if choice in self.drive_combo.cget("values") else 0
        if selected_index < len(self.drives):
            self.selected_drive = self.drives[selected_index]
            drive_path = self.selected_drive.get("path")
            self.executor = ATACommandExecutor(drive_path)
            self._log(f"Dispositivo seleccionado: {drive_path} ({self.selected_drive.get('model')})")
            
            self.lbl_model.configure(text=f"Modelo: {self.selected_drive.get('model')[:25]}")
            self.lbl_serial.configure(text=f"Serial: {self.selected_drive.get('serial') or '-'}")
            self.lbl_firmware.configure(text=f"Interfaz: {self.selected_drive.get('interface')}")
            self.lbl_capacity.configure(text=f"Capacidad: {self.selected_drive.get('size_str')}")

    def _on_preset_selected(self, preset):
        if "IDENTIFY" in preset:
            self.reg_entries["txt_reg_cmd"].delete(0, "end"); self.reg_entries["txt_reg_cmd"].insert(0, "EC")
            self.reg_entries["txt_reg_feat"].delete(0, "end"); self.reg_entries["txt_reg_feat"].insert(0, "00")
            self.reg_entries["txt_reg_sc"].delete(0, "end"); self.reg_entries["txt_reg_sc"].insert(0, "1")
            self.reg_entries["txt_reg_lba"].delete(0, "end"); self.reg_entries["txt_reg_lba"].insert(0, "0")
            self.reg_entries["txt_reg_buf"].delete(0, "end"); self.reg_entries["txt_reg_buf"].insert(0, "512")
            self.reg_entries["combo_reg_dir"].set("in")
        elif "SMART READ DATA" in preset:
            self.reg_entries["txt_reg_cmd"].delete(0, "end"); self.reg_entries["txt_reg_cmd"].insert(0, "B0")
            self.reg_entries["txt_reg_feat"].delete(0, "end"); self.reg_entries["txt_reg_feat"].insert(0, "D0")
            self.reg_entries["txt_reg_sc"].delete(0, "end"); self.reg_entries["txt_reg_sc"].insert(0, "1")
            self.reg_entries["txt_reg_lba"].delete(0, "end"); self.reg_entries["txt_reg_lba"].insert(0, "0xC24F00")
            self.reg_entries["txt_reg_buf"].delete(0, "end"); self.reg_entries["txt_reg_buf"].insert(0, "512")
            self.reg_entries["combo_reg_dir"].set("in")
        elif "SMART RETURN STATUS" in preset:
            self.reg_entries["txt_reg_cmd"].delete(0, "end"); self.reg_entries["txt_reg_cmd"].insert(0, "B0")
            self.reg_entries["txt_reg_feat"].delete(0, "end"); self.reg_entries["txt_reg_feat"].insert(0, "DA")
            self.reg_entries["txt_reg_sc"].delete(0, "end"); self.reg_entries["txt_reg_sc"].insert(0, "0")
            self.reg_entries["txt_reg_lba"].delete(0, "end"); self.reg_entries["txt_reg_lba"].insert(0, "0xC24F00")
            self.reg_entries["txt_reg_buf"].delete(0, "end"); self.reg_entries["txt_reg_buf"].insert(0, "0")
            self.reg_entries["combo_reg_dir"].set("none")
        elif "CHECK POWER" in preset:
            self.reg_entries["txt_reg_cmd"].delete(0, "end"); self.reg_entries["txt_reg_cmd"].insert(0, "E5")
            self.reg_entries["txt_reg_feat"].delete(0, "end"); self.reg_entries["txt_reg_feat"].insert(0, "00")
            self.reg_entries["txt_reg_sc"].delete(0, "end"); self.reg_entries["txt_reg_sc"].insert(0, "0")
            self.reg_entries["txt_reg_lba"].delete(0, "end"); self.reg_entries["txt_reg_lba"].insert(0, "0")
            self.reg_entries["txt_reg_buf"].delete(0, "end"); self.reg_entries["txt_reg_buf"].insert(0, "0")
            self.reg_entries["combo_reg_dir"].set("none")
        elif "READ SECTORS" in preset:
            self.reg_entries["txt_reg_cmd"].delete(0, "end"); self.reg_entries["txt_reg_cmd"].insert(0, "20")
            self.reg_entries["txt_reg_feat"].delete(0, "end"); self.reg_entries["txt_reg_feat"].insert(0, "00")
            self.reg_entries["txt_reg_sc"].delete(0, "end"); self.reg_entries["txt_reg_sc"].insert(0, "1")
            self.reg_entries["txt_reg_lba"].delete(0, "end"); self.reg_entries["txt_reg_lba"].insert(0, "0")
            self.reg_entries["txt_reg_buf"].delete(0, "end"); self.reg_entries["txt_reg_buf"].insert(0, "512")
            self.reg_entries["combo_reg_dir"].set("in")

    def _cmd_identify(self):
        if not self.executor:
            return
        def worker():
            self._log("Enviando ATA IDENTIFY DEVICE (0xEC)...")
            try:
                res = self.executor.identify_device()
                if res.get("success"):
                    self.lbl_model.configure(text=f"Modelo: {res.get('model')}")
                    self.lbl_serial.configure(text=f"Serial: {res.get('serial')}")
                    self.lbl_firmware.configure(text=f"Firmware: {res.get('firmware')}")
                    self.lbl_capacity.configure(text=f"Capacidad: {res.get('capacity_gb', 0):.2f} GB ({res.get('rpm')})")
                    self._log(f"IDENTIFY Éxito: {res.get('model')} | SN: {res.get('serial')} | Sectores: {res.get('total_sectors'):,}")
                    self.raw_hex_view.display_data(res.get("raw_data"))
                else:
                    self._log(f"Error en ATA IDENTIFY: {res.get('error')}")
            except Exception as e:
                self._log(f"Excepción en IDENTIFY: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_read_smart(self):
        if not self.executor:
            return
        def worker():
            self._log("Leyendo atributos SMART (0xB0, subcomando 0xD0)...")
            try:
                res = self.executor.read_smart_data()
                if res.get("success"):
                    # Clear treeview
                    for item in self.smart_tree.get_children():
                        self.smart_tree.delete(item)

                    critical_found = False
                    for attr in res.get("attributes", []):
                        risk = "NORMAL"
                        # High risk attributes: 5 (Reallocated Sectors), 187, 197 (Current Pending), 198 (Offline Uncorrectable)
                        if attr["id"] in (5, 187, 197, 198) and attr["raw"] > 0:
                            risk = "ALERTA / RIESGO"
                            critical_found = True

                        self.smart_tree.insert("", "end", values=(
                            attr["id"],
                            attr["name"],
                            attr["current"],
                            attr["worst"],
                            attr["raw_str"],
                            risk
                        ))

                    if critical_found:
                        self.lbl_health_badge.configure(text="Estado: ⚠️ SECTORES DAÑADOS / RIESGO", text_color="#ff5555")
                    else:
                        self.lbl_health_badge.configure(text="Estado: ✅ SALUD BUENA", text_color="#55ff55")

                    self._log(f"Atributos SMART leídos: {len(res.get('attributes', []))} atributos.")
                else:
                    self._log(f"Error leyendo SMART: {res.get('error')}")
            except Exception as e:
                self._log(f"Excepción leyendo SMART: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_smart_status(self):
        if not self.executor:
            return
        def worker():
            self._log("Comprobando estado de salud SMART (0xB0 / 0xDA)...")
            try:
                res = self.executor.check_smart_status()
                status_str = res.get("status_str", "Desconocido")
                if res.get("threshold_exceeded"):
                    self.lbl_health_badge.configure(text=f"Estado: ❌ {status_str}", text_color="#ff4444")
                else:
                    self.lbl_health_badge.configure(text=f"Estado: 🟢 {status_str}", text_color="#44ff44")
                self._log(f"Resultado SMART Status: {status_str} | Registros: {res.get('registers')}")
            except Exception as e:
                self._log(f"Excepción comprobando SMART status: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_read_lba(self):
        if not self.executor:
            return
        try:
            lba_str = self.txt_lba_target.get().strip()
            lba = int(lba_str, 16) if lba_str.lower().startswith("0x") else int(lba_str)
        except ValueError:
            messagebox.showerror("Error de Entrada", "Dirección LBA no válida.")
            return

        def worker():
            self._log(f"Leyendo LBA {lba}...")
            try:
                res = self.executor.read_sector(lba)
                if res.get("success") and res.get("data"):
                    self.lba_hex_view.display_data(res.get("data"), base_offset=lba * 512)
                    self._log(f"LBA {lba} leído con éxito (512 bytes).")
                else:
                    self._log(f"Fallo al leer LBA {lba}. Error Win32 / SCSI Status.")
            except Exception as e:
                self._log(f"Excepción leyendo LBA: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _setup_smart_ops_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure(0, weight=1)

        # Warning & Architecture Explanation Card
        banner = ctk.CTkFrame(scroll, fg_color=("#374151", "#1e293b"), corner_radius=8)
        banner.pack(fill="x", pady=(0, 10), padx=5)

        ctk.CTkLabel(
            banner,
            text="⚠️ Cómo Funciona el Restablecimiento de SMART y Limpieza de Sectores Defectuosos",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        info_text = (
            "1. Comandos ATA Estándar (Case USB): La norma ATA permite Habilitar, Deshabilitar y Ejecutar Pruebas (Self-Tests), "
            "pero PROHÍBE que un comando estándar de usuario borre el historial de sectores reasignados (ID 5 / 197) para evitar fraudes.\n\n"
            "2. Para Restablecer Contadores SMART y la G-List de Sectores Reasignados:\n"
            "   Es necesario acceder a la Terminal de Diagnóstico Serial/TTL (Pestaña 'Terminal Serial') o enviar Comandos de Fabricante (VSC) "
            "directos al microcódigo del PCB."
        )
        ctk.CTkLabel(
            banner,
            text=info_text,
            font=ctk.CTkFont(size=11),
            text_color="gray80",
            justify="left",
            wraplength=850
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # Seagate F3 Section Card
        card_seagate = ctk.CTkFrame(scroll, fg_color=("gray90", "gray17"), corner_radius=8)
        card_seagate.pack(fill="x", pady=6, padx=5)
        card_seagate.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_seagate, text="🔵 Seagate F3 (Barracuda, 7200.11, 7200.12, Rosewood)", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        
        seagate_guide = (
            "Secuencia de Limpieza y Reconstrucción en Terminal Serial (UART 38400 baudios):\n"
            "  Paso 1: Presiona [Ctrl+Z] hasta ver el prompt 'F3 T>'\n"
            "  Paso 2: Escribe '/T' y luego 'i4,1,22' (Limpia la G-List de sectores reasignados).\n"
            "  Paso 3: Escribe '/1' y luego 'N1,,22' (Resetea los contadores y atributos SMART a 0).\n"
            "  Paso 4: Escribe '/T' y luego 'm0,6,2,,,,,22' o 'm0,2,2,,,,,22' (Regenera la tabla de traducción LBA / Formatea partición de usuario).\n"
            "  Paso 5: Apaga y enciende el disco (Power Cycle)."
        )
        ctk.CTkLabel(card_seagate, text=seagate_guide, font=("Consolas", 10), justify="left", text_color="#a5f3fc").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        # Western Digital Section Card
        card_wd = ctk.CTkFrame(scroll, fg_color=("gray90", "gray17"), corner_radius=8)
        card_wd.pack(fill="x", pady=6, padx=5)
        card_wd.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_wd, text="🔴 Western Digital (WD Marvel / ROYL Architecture)", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        
        wd_guide = (
            "Secuencia de Limpieza en WD:\n"
            "  1. Desbloqueo SuperOn: Enviar clave VSC SuperOn (Habilita escritura en Service Area).\n"
            "  2. Limpieza de SMART: Formatear / Limpiar el Módulo de Firmware 0x21 (SMART Table).\n"
            "  3. Limpieza de G-List: Limpiar Módulo 0x32 (G-List Table) y regenerar Translator (Módulo 0x33).\n"
            "  4. Terminal Serie WD: Ejecutar comandos 'CLRG' y 'CLRDEF'."
        )
        ctk.CTkLabel(card_wd, text=wd_guide, font=("Consolas", 10), justify="left", text_color="#fecaca").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

        # Toshiba / Hitachi Section Card
        card_tosh = ctk.CTkFrame(scroll, fg_color=("gray90", "gray17"), corner_radius=8)
        card_tosh.pack(fill="x", pady=6, padx=5)
        card_tosh.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card_tosh, text="🟢 Toshiba & Hitachi / HGST", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))
        
        tosh_guide = (
            "Procedimiento en Terminal Serial:\n"
            "  1. Conectar a 9600 o 115200 baudios y presionar Enter para despertar consola.\n"
            "  2. Toshiba: Comando '/ -> M0' para realizar Low-Level Format y regeneración de tablas P/G.\n"
            "  3. Hitachi: VSC directos para borrado de NV-RAM SMART."
        )
        ctk.CTkLabel(card_tosh, text=tosh_guide, font=("Consolas", 10), justify="left", text_color="#bbf7d0").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

    def _cmd_smart_toggle(self, enable: bool):
        if not self.executor:
            return
        action_name = "Habilitando" if enable else "Deshabilitando"
        def worker():
            self._log(f"{action_name} subsistema SMART ATA (0xB0 / {'0xD8' if enable else '0xD9'})...")
            try:
                res = self.executor.smart_enable() if enable else self.executor.smart_disable()
                self._log(f"SMART {'Habilitado' if enable else 'Deshabilitado'} con éxito: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción al modificar SMART: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_run_selftest(self, test_type: str):
        if not self.executor:
            return
        def worker():
            self._log(f"Enviando comando SMART Self-Test ({test_type.upper()})...")
            try:
                res = self.executor.smart_self_test(test_type)
                self._log(f"Self-Test {test_type} iniciado: Éxito={res.get('success')}")
            except Exception as e:
                self._log(f"Excepción en Self-Test: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _cmd_execute_raw(self):
        if not self.executor:
            return
        try:
            cmd = int(self.reg_entries["txt_reg_cmd"].get().strip(), 16)
            feat = int(self.reg_entries["txt_reg_feat"].get().strip(), 16)
            sc = int(self.reg_entries["txt_reg_sc"].get().strip())
            
            lba_str = self.reg_entries["txt_reg_lba"].get().strip()
            lba = int(lba_str, 16) if lba_str.lower().startswith("0x") else int(lba_str)
            
            dev = int(self.reg_entries["txt_reg_dev"].get().strip(), 16)
            buf_size = int(self.reg_entries["txt_reg_buf"].get().strip())
            direction = self.reg_entries["combo_reg_dir"].get().strip()
            is_lba48 = bool(self.chk_lba48.get())
        except ValueError as e:
            messagebox.showerror("Error en Registro", f"Formato numérico no válido: {e}")
            return

        def worker():
            self._log(f"Ejecutando comando RAW ATA: Opcode=0x{cmd:02X}, Feat=0x{feat:02X}, LBA={lba}, SC={sc}...")
            try:
                res = self.executor.execute_raw_command(
                    command=cmd,
                    features=feat,
                    sector_count=sc,
                    lba=lba,
                    device=dev,
                    buffer_size=buf_size,
                    direction=direction,
                    is_lba48=is_lba48
                )
                regs = res.get("ata_registers", {})
                ret_str = f"Status=0x{regs.get('status', 0):02X} Error=0x{regs.get('error', 0):02X} LBA=0x{regs.get('lba', 0):X} Dev=0x{regs.get('device', 0):02X}"
                self.lbl_raw_return.configure(text=f"Registros devueltos: {ret_str}")
                
                if res.get("data"):
                    self.raw_hex_view.display_data(res.get("data"))
                else:
                    self.raw_hex_view.set_empty_text("Comando sin buffer de datos devuelto.")
                
                self._log(f"Comando ATA finalizado: Éxito={res.get('success')} | {ret_str}")
            except Exception as e:
                self._log(f"Excepción en comando RAW: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[ATA-USB] {text}")

