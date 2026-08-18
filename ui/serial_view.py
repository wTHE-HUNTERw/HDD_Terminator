"""
Serial / UART Firmware Terminal View
Interactive console for HDD PCB diagnostics (Seagate F3, WD, Toshiba) via USB-TTL adaptors.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.drive_detector import get_serial_ports
from core.serial_terminal import SerialTerminalManager, FIRMWARE_MACROS

class SerialViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.serial_manager = SerialTerminalManager(
            data_received_callback=self._on_serial_data_received,
            status_callback=self._on_serial_status_change
        )
        self.available_ports = []
        self._setup_ui()
        self.refresh_ports()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Connection Config Bar
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_bar, text="Puerto COM:", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, padx=(10, 4), pady=8)
        
        self.combo_ports = ctk.CTkComboBox(top_bar, values=["Escaneando..."], width=180)
        self.combo_ports.grid(row=0, column=1, padx=4, pady=8, sticky="w")

        ctk.CTkLabel(top_bar, text="Baudios:").grid(row=0, column=2, padx=(10, 4), pady=8)
        self.combo_baud = ctk.CTkComboBox(
            top_bar,
            values=["38400", "9600", "19200", "57600", "115200", "230400", "460800"],
            width=100
        )
        self.combo_baud.set("38400") # Default for Seagate F3
        self.combo_baud.grid(row=0, column=3, padx=4, pady=8)

        self.btn_refresh_ports = ctk.CTkButton(top_bar, text="🔄", width=36, command=self.refresh_ports)
        self.btn_refresh_ports.grid(row=0, column=4, padx=4, pady=8)

        self.btn_connect = ctk.CTkButton(
            top_bar,
            text="⚡ Conectar",
            width=110,
            fg_color="#2b7a4b",
            hover_color="#1e5a36",
            command=self._toggle_connection
        )
        self.btn_connect.grid(row=0, column=5, padx=10, pady=8)

        # Left Column: Terminal Output & Input
        term_panel = ctk.CTkFrame(self, fg_color="transparent")
        term_panel.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        term_panel.grid_columnconfigure(0, weight=1)
        term_panel.grid_rowconfigure(0, weight=1)

        self.term_box = ctk.CTkTextbox(
            term_panel,
            font=("Consolas", 12),
            fg_color="#0a0a0a",
            text_color="#00ff66",
            activate_scrollbars=True
        )
        self.term_box.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=(0, 5))

        # Bottom Command Input
        self.txt_cmd_input = ctk.CTkEntry(
            term_panel,
            placeholder_text="Escribe un comando para el disco (ej. /1, N1, m0,2,2,0,0,0,0,22, Ctrl+Z)...",
            font=("Consolas", 12)
        )
        self.txt_cmd_input.grid(row=1, column=0, sticky="ew", padx=(0, 5))
        self.txt_cmd_input.bind("<Return>", lambda e: self._send_typed_command())

        self.btn_send_cmd = ctk.CTkButton(
            term_panel,
            text="Enviar (Enter)",
            width=110,
            command=self._send_typed_command
        )
        self.btn_send_cmd.grid(row=1, column=1, padx=2)

        self.btn_clear_term = ctk.CTkButton(
            term_panel,
            text="Limpiar",
            width=70,
            fg_color="gray30",
            command=self._clear_terminal
        )
        self.btn_clear_term.grid(row=1, column=2, padx=(2, 0))

        # Right Column: Firmware Diagnostics & Macro Tools
        right_panel = ctk.CTkFrame(self, fg_color=("gray90", "gray14"))
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(right_panel, text="Macros & Presets de Firmware", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, pady=8)

        # Manufacturer Selector Tab
        self.combo_vendor = ctk.CTkSegmentedButton(
            right_panel,
            values=["Seagate F3", "Western Digital", "Toshiba"],
            command=self._render_macros
        )
        self.combo_vendor.set("Seagate F3")
        self.combo_vendor.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        # Scrollable Frame for Macros
        self.macro_scroll_frame = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        self.macro_scroll_frame.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self.macro_scroll_frame.grid_columnconfigure(0, weight=1)

        # Quick Control Signals
        signal_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        signal_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        signal_frame.grid_columnconfigure((0, 1, 2), weight=1)

        btn_ctrl_z = ctk.CTkButton(signal_frame, text="Ctrl+Z", fg_color="#d97706", hover_color="#b45309", command=self.serial_manager.send_ctrl_z)
        btn_ctrl_z.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

        btn_ctrl_c = ctk.CTkButton(signal_frame, text="Ctrl+C", fg_color="#dc2626", hover_color="#991b1b", command=self.serial_manager.send_ctrl_c)
        btn_ctrl_c.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        btn_break = ctk.CTkButton(signal_frame, text="Break", fg_color="#4b5563", hover_color="#374151", command=self.serial_manager.send_break)
        btn_break.grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        btn_export = ctk.CTkButton(right_panel, text="💾 Guardar Log de Terminal", fg_color="#2563eb", command=self._export_log)
        btn_export.grid(row=4, column=0, padx=8, pady=(0, 8), sticky="ew")

        self._render_macros("Seagate F3")

    def refresh_ports(self):
        self.available_ports = get_serial_ports()
        port_names = [f"{p['port']} ({p['description'][:20]})" for p in self.available_ports]
        if not port_names:
            port_names = ["No hay puertos COM"]
        self.combo_ports.configure(values=port_names)
        self.combo_ports.set(port_names[0])

    def _toggle_connection(self):
        if self.serial_manager.is_connected:
            self.serial_manager.disconnect()
        else:
            selected_str = self.combo_ports.get()
            port_name = selected_str.split(" ")[0] if selected_str else ""
            if not port_name or port_name == "No":
                messagebox.showerror("Error", "Selecciona un puerto COM válido.")
                return
            baud = int(self.combo_baud.get())
            self.serial_manager.connect(port=port_name, baudrate=baud)

    def _on_serial_status_change(self, connected: bool, message: str):
        if connected:
            self.btn_connect.configure(text="❌ Desconectar", fg_color="#dc2626", hover_color="#991b1b")
        else:
            self.btn_connect.configure(text="⚡ Conectar", fg_color="#2b7a4b", hover_color="#1e5a36")
        self._append_terminal(f"\n[SISTEMA] {message}\n")
        if self.log_callback:
            self.log_callback(f"[SERIAL] {message}")

    def _on_serial_data_received(self, raw_bytes: bytes, text: str):
        self._append_terminal(text)

    def _append_terminal(self, text: str):
        self.term_box.insert("end", text)
        self.term_box.see("end")

    def _clear_terminal(self):
        self.term_box.delete("1.0", "end")

    def _send_typed_command(self):
        cmd = self.txt_cmd_input.get()
        if not cmd:
            return
        self.txt_cmd_input.delete(0, "end")
        if not self.serial_manager.is_connected:
            self._append_terminal(f"\n[ALERTA] Puerto serial no conectado. No se pudo enviar: {cmd}\n")
            return
        
        # Check special keystrokes
        if cmd.lower() in ("ctrl+z", "^z"):
            self.serial_manager.send_ctrl_z()
            self._append_terminal("[ENVIADO: Ctrl+Z (0x1A)]\n")
        elif cmd.lower() in ("ctrl+c", "^c"):
            self.serial_manager.send_ctrl_c()
            self._append_terminal("[ENVIADO: Ctrl+C (0x03)]\n")
        else:
            self.serial_manager.send_text(cmd)
            self._append_terminal(f"\n> {cmd}\n")

    def _render_macros(self, vendor: str):
        # Auto-adjust recommended baudrate
        if vendor == "Seagate F3":
            self.combo_baud.set("38400")
        elif vendor == "Western Digital":
            self.combo_baud.set("115200")
        elif vendor == "Toshiba":
            self.combo_baud.set("9600")

        for widget in self.macro_scroll_frame.winfo_children():
            widget.destroy()

        macros = FIRMWARE_MACROS.get(vendor, [])
        for m in macros:
            card = ctk.CTkFrame(self.macro_scroll_frame, fg_color=("gray85", "gray20"), corner_radius=6, border_width=1, border_color="#334155")
            card.pack(fill="x", pady=4, padx=2)
            card.grid_columnconfigure(0, weight=1)

            lbl_title = ctk.CTkLabel(card, text=m["name"], font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8")
            lbl_title.grid(row=0, column=0, sticky="w", padx=8, pady=(5, 0))

            lbl_desc = ctk.CTkLabel(card, text=m["desc"], font=ctk.CTkFont(size=10), text_color="gray70", wraplength=210, justify="left")
            lbl_desc.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 5))

            btn_exec = ctk.CTkButton(
                card,
                text="Enviar ▶",
                width=70,
                height=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#0284c7",
                hover_color="#0369a1",
                command=lambda item=m: self._execute_macro(item)
            )
            btn_exec.grid(row=0, column=1, rowspan=2, padx=8, pady=5)

    def _execute_macro(self, macro_item: dict):
        if not self.serial_manager.is_connected:
            messagebox.showwarning("No Conectado", "Conecta primero el puerto serial/TTL.")
            return

        action = macro_item.get("action")
        data = macro_item.get("data")
        name = macro_item.get("name")

        self._append_terminal(f"\n[EJECUTANDO MACRO: {name}]\n")
        if action == "raw":
            self.serial_manager.send_raw_bytes(data)
        elif action == "text":
            self.serial_manager.send_text(data, append_newline=False)

    def _export_log(self):
        log_content = self.term_box.get("1.0", "end").strip()
        if not log_content:
            messagebox.showinfo("Log Vacío", "No hay contenido en la terminal para guardar.")
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Archivos de Log", "*.log"), ("Archivos de Texto", "*.txt"), ("Todos los archivos", "*.*")],
            title="Guardar sesión de terminal"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                messagebox.showinfo("Guardado", f"Log guardado exitosamente en:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar el archivo: {e}")
