"""
Universal Health Overview & Quick Health Check Dashboard
Clean, intuitive 1-click diagnostic summary for any connected drive.
"""

import threading
import customtkinter as ctk
from core.ata_commands import ATACommandExecutor

class OverviewViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, on_navigate=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.on_navigate = on_navigate
        self.current_drive = None
        self.executor = None

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        scroll.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 0. Drive Selector Bar on Overview Dashboard
        top_sel_card = ctk.CTkFrame(scroll, fg_color=("#111827", "#1e293b"), corner_radius=10, border_width=1, border_color="#334155")
        top_sel_card.grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=(6, 10))
        top_sel_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top_sel_card,
            text="💽 Seleccionar Disco Objetivo:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        ).grid(row=0, column=0, padx=(14, 6), pady=10)

        self.combo_overview_drives = ctk.CTkComboBox(
            top_sel_card,
            values=["Escaneando discos..."],
            command=self._on_drive_combo_selected,
            width=380,
            font=ctk.CTkFont(size=12)
        )
        self.combo_overview_drives.grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        btn_refresh_ov = ctk.CTkButton(
            top_sel_card,
            text="🔄 Actualizar Discos",
            width=140,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._on_refresh_clicked
        )
        btn_refresh_ov.grid(row=0, column=2, padx=(6, 14), pady=10)

        # 1. Hero Banner: Quick Health Status Card
        self.hero_card = ctk.CTkFrame(scroll, fg_color=("#111827", "#0f172a"), corner_radius=12, border_width=1, border_color="#1e293b")
        self.hero_card.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=(4, 15))
        self.hero_card.grid_columnconfigure(1, weight=1)

        self.lbl_health_icon = ctk.CTkLabel(self.hero_card, text="🩺", font=ctk.CTkFont(size=42))
        self.lbl_health_icon.grid(row=0, column=0, rowspan=2, padx=(20, 10), pady=15)

        self.lbl_health_title = ctk.CTkLabel(
            self.hero_card,
            text="Evaluación de Salud del Disco",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_health_title.grid(row=0, column=1, sticky="w", pady=(15, 2))

        self.lbl_health_desc = ctk.CTkLabel(
            self.hero_card,
            text="Selecciona una unidad para analizar su estado SMART, sectores defectuosos y temperatura.",
            font=ctk.CTkFont(size=12),
            text_color="gray70"
        )
        self.lbl_health_desc.grid(row=1, column=1, sticky="w", pady=(0, 15))

        self.btn_quick_scan = ctk.CTkButton(
            self.hero_card,
            text="⚡ Diagnóstico Rápido de 1-Clic",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=38,
            command=self.run_quick_diagnosis
        )
        self.btn_quick_scan.grid(row=0, column=2, rowspan=2, padx=20, pady=15)

        # 2. Metric KPI Cards (4 Cards)
        self.card_model = self._create_kpi_card(scroll, 2, 0, "🏷️ MODELO & MARCA", "-", "#38bdf8", "Fabricante detectado")
        self.card_health = self._create_kpi_card(scroll, 2, 1, "❤️ ESTADO DE SALUD", "Pendiente", "#10b981", "Evaluación SMART")
        self.card_temp = self._create_kpi_card(scroll, 2, 2, "🌡️ TEMPERATURA", "-- °C", "#f59e0b", "Temperatura de operación")
        self.card_bad = self._create_kpi_card(scroll, 2, 3, "⚠️ SECTORES DAÑADOS", "0", "#ef4444", "Reasignados + Pendientes")

        # 3. Quick Action Hub (Clean cards with icons and descriptions)
        ctk.CTkLabel(
            scroll,
            text="🚀 Acciones Rápidas & Tratamiento Recomendado",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e2e8f0"
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=12, pady=(20, 8))

        actions = [
            ("🧹 Formateo a Bajo Nivel", "Limpia y sobreescribe todos los sectores con visualizador en vivo.", "format", "#dc2626"),
            ("📊 Análisis SMART Completo", "Revisa la lista de 30 atributos SMART y umbrales de fallo.", "smart", "#15803d"),
            ("🛠️ Limpiar Sectores / G-List", "Guías y comandos para borrar sectores reasignados por marca.", "reset", "#7c3aed"),
            ("🔌 Terminal Serial de Firmware", "Accede a la consola de microcódigo UART (Seagate, WD, Toshiba).", "serial", "#0284c7"),
            ("💾 Modding SPI (Winbond 25Q80)", "Edita y desbloquea volcados de memoria ROM para CH341A.", "spi", "#d97706"),
            ("⚡ ATA Sanitize & Security", "Purga de bajo nivel mediante microcódigo de controladora.", "sanitize", "#b45309")
        ]

        for idx, (title, desc, nav_target, color) in enumerate(actions):
            r = 3 + (idx // 3)
            c = (idx % 3)
            # Expand to fill 3-column span nicely
            self._create_action_card(scroll, r, c, title, desc, nav_target, color)

    def _create_kpi_card(self, parent, row, col, title, value, val_color, subtitle):
        card = ctk.CTkFrame(parent, fg_color=("gray90", "gray14"), corner_radius=10, border_width=1, border_color="#1e293b")
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=4)
        card.grid_columnconfigure(0, weight=1)

        lbl_t = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="gray60")
        lbl_t.pack(anchor="w", padx=12, pady=(10, 2))

        lbl_v = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=16, weight="bold"), text_color=val_color)
        lbl_v.pack(anchor="w", padx=12, pady=(0, 2))

        lbl_s = ctk.CTkLabel(card, text=subtitle, font=ctk.CTkFont(size=9), text_color="gray50")
        lbl_s.pack(anchor="w", padx=12, pady=(0, 10))

        return {"title": lbl_t, "val": lbl_v, "sub": lbl_s}

    def _create_action_card(self, parent, row, col, title, desc, nav_target, btn_color):
        card = ctk.CTkFrame(parent, fg_color=("gray90", "gray14"), corner_radius=10, border_width=1, border_color="#1e293b")
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="#f8fafc").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(card, text=desc, font=ctk.CTkFont(size=10), text_color="gray70", justify="left", wraplength=260).pack(anchor="w", padx=12, pady=(0, 10))

        btn = ctk.CTkButton(
            card,
            text="Abrir Herramienta ▶",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=btn_color,
            height=28,
            command=lambda: self._navigate(nav_target)
        )
        btn.pack(fill="x", padx=12, pady=(0, 10))

    def update_drive_list(self, drives: list):
        self.drives = drives
        combo_values = []
        for d in self.drives:
            usb_tag = "[USB] " if d.get("is_usb") else ""
            letters_tag = f"({d.get('letters')})" if d.get("letters") else ""
            combo_values.append(f"{usb_tag}{d.get('path')} - {d.get('model')} - {d.get('size_str')} {letters_tag}")
        
        if not combo_values:
            combo_values = ["No se detectaron discos físicos"]

        self.combo_overview_drives.configure(values=combo_values)
        if combo_values and self.combo_overview_drives.get() not in combo_values:
            self.combo_overview_drives.set(combo_values[0])
            self._on_drive_combo_selected(combo_values[0])

    def _on_drive_combo_selected(self, choice: str):
        if not hasattr(self, "drives") or not self.drives:
            return
        vals = self.combo_overview_drives.cget("values")
        selected_index = vals.index(choice) if choice in vals else 0
        if selected_index < len(self.drives):
            drive_dict = self.drives[selected_index]
            self.set_drive(drive_dict)
            if hasattr(self, "on_drive_changed_callback") and self.on_drive_changed_callback:
                self.on_drive_changed_callback(drive_dict)

    def _on_refresh_clicked(self):
        if hasattr(self, "on_refresh_callback") and self.on_refresh_callback:
            self.on_refresh_callback()

    def set_drive(self, drive_dict):
        self.current_drive = drive_dict
        if drive_dict:
            path = drive_dict.get("path")
            self.executor = ATACommandExecutor(path)
            model = drive_dict.get("model", "Desconocido")
            self.card_model["val"].configure(text=model[:20])
            self.card_model["sub"].configure(text=f"{drive_dict.get('size_str')} | {drive_dict.get('interface')}")
            self.lbl_health_title.configure(text=f"{model}")
            self.lbl_health_desc.configure(text=f"Unidad seleccionada: {path} ({drive_dict.get('size_str')})")
            
            # Sync combo text if not set
            if hasattr(self, "drives") and self.drives:
                for idx, d in enumerate(self.drives):
                    if d.get("path") == path:
                        vals = self.combo_overview_drives.cget("values")
                        if idx < len(vals):
                            self.combo_overview_drives.set(vals[idx])
                        break
        else:
            self.card_model["val"].configure(text="Sin Disco")
            self.card_model["sub"].configure(text="-")

    def run_quick_diagnosis(self):
        if not self.executor or not self.current_drive:
            return

        def worker():
            self._log("Iniciando Diagnóstico Rápido Universal...")
            try:
                # 1. Identify
                ident = self.executor.identify_device()
                if ident.get("success"):
                    self.card_model["val"].configure(text=ident.get("model")[:20])
                    self.card_model["sub"].configure(text=f"SN: {ident.get('serial')}")

                # 2. SMART Status & Attributes
                smart_res = self.executor.read_smart_data()
                if smart_res.get("success"):
                    attrs = smart_res.get("attributes", [])
                    reallocated = 0
                    pending = 0
                    temp_c = "--"
                    
                    for a in attrs:
                        if a["id"] == 5:
                            reallocated = a["raw"]
                        elif a["id"] == 197:
                            pending = a["raw"]
                        elif a["id"] in (194, 190) and temp_c == "--":
                            temp_c = str(a["raw"] & 0xFF)

                    total_bad = reallocated + pending
                    self.card_temp["val"].configure(text=f"{temp_c} °C" if temp_c != "--" else "N/A")
                    self.card_bad["val"].configure(text=str(total_bad))

                    if total_bad > 0:
                        self.card_bad["val"].configure(text_color="#ef4444")
                        self.card_health["val"].configure(text="⚠️ RIESGO", text_color="#ef4444")
                        self.card_health["sub"].configure(text=f"{reallocated} reasig. / {pending} pend.")
                        self.lbl_health_icon.configure(text="⚠️")
                        self.lbl_health_title.configure(text=f"Atención: {total_bad} sectores defectuosos detectados")
                    else:
                        self.card_bad["val"].configure(text_color="#10b981")
                        self.card_health["val"].configure(text="✅ ÓPTIMA (100%)", text_color="#10b981")
                        self.card_health["sub"].configure(text="0 sectores dañados")
                        self.lbl_health_icon.configure(text="✅")
                        self.lbl_health_title.configure(text="Salud del Disco: Excelente (Sin fallos)")

                    self._log(f"Diagnóstico completado: Salud={self.card_health['val'].cget('text')} | Temp={temp_c}°C | Bad={total_bad}")
                else:
                    self.card_health["val"].configure(text="No disponible", text_color="gray")
                    self._log(f"SMART no accesible directamente por el bridge USB: {smart_res.get('error')}")
            except Exception as e:
                self._log(f"Error durante el diagnóstico rápido: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _navigate(self, target: str):
        if self.on_navigate:
            self.on_navigate(target)

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[OVERVIEW] {text}")
