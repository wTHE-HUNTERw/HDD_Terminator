"""
Interactive SPI Flash ROM Editor & Firmware Patcher View
Dedicated to Winbond 25Q80 (1MB) / 25Q16 (2MB) and CH341A / CH340 USB Programmer Dumps.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

from core.spi_editor import SPIROMPatcher
from core.spi_flash import Winbond25Q80ROMInspector

class SPIEditorViewFrame(ctk.CTkFrame):
    def __init__(self, master, log_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.log_callback = log_callback
        self.patcher = None
        self.current_filepath = None
        self.current_offset = 0
        self.page_size = 512

        self._setup_ui()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Control Bar: File loading, saving & offsets
        top_bar = ctk.CTkFrame(self, fg_color=("gray85", "gray17"), corner_radius=8)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))
        top_bar.grid_columnconfigure(1, weight=1)

        btn_open = ctk.CTkButton(
            top_bar,
            text="📂 Abrir Archivo ROM (.bin / .rom)",
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._cmd_open_rom
        )
        btn_open.grid(row=0, column=0, padx=(10, 4), pady=8)

        self.lbl_file_info = ctk.CTkLabel(
            top_bar,
            text="Ningún archivo cargado. Abre un volcado del CH341A / Winbond 25Q80.",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        self.lbl_file_info.grid(row=0, column=1, padx=8, pady=8, sticky="w")

        self.btn_save = ctk.CTkButton(
            top_bar,
            text="💾 Guardar ROM Parcheada",
            fg_color="#15803d",
            hover_color="#166534",
            command=self._cmd_save_rom,
            state="disabled"
        )
        self.btn_save.grid(row=0, column=2, padx=(4, 10), pady=8)

        # Left Column: Hex & ASCII Interactive Editor
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=1)

        # Navigation Bar
        nav_bar = ctk.CTkFrame(left_panel, fg_color=("gray90", "gray14"), corner_radius=6)
        nav_bar.grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(nav_bar, text="Offset (Hex):", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(10, 4), pady=4)
        self.txt_offset_input = ctk.CTkEntry(nav_bar, width=110, placeholder_text="0x000000")
        self.txt_offset_input.insert(0, "0x000000")
        self.txt_offset_input.pack(side="left", padx=4, pady=4)

        btn_go_offset = ctk.CTkButton(nav_bar, text="Ir a Offset", width=85, command=self._cmd_go_offset)
        btn_go_offset.pack(side="left", padx=4, pady=4)

        btn_prev = ctk.CTkButton(nav_bar, text="◀ Anterior (512B)", width=120, command=self._cmd_prev_page)
        btn_prev.pack(side="left", padx=(10, 4), pady=4)

        btn_next = ctk.CTkButton(nav_bar, text="Siguiente (512B) ▶", width=120, command=self._cmd_next_page)
        btn_next.pack(side="left", padx=4, pady=4)

        # Search Bar
        ctk.CTkLabel(nav_bar, text="Buscar:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left", padx=(15, 4), pady=4)
        self.txt_search = ctk.CTkEntry(nav_bar, width=130, placeholder_text="Texto o Hex...")
        self.txt_search.pack(side="left", padx=4, pady=4)
        self.txt_search.bind("<Return>", lambda e: self._cmd_search())

        btn_search = ctk.CTkButton(nav_bar, text="🔍 Buscar", width=75, command=self._cmd_search)
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
        self.hex_editor.insert("1.0", "--- Carga un archivo de volcado SPI Flash (.bin / .rom) para editar ---")

        # Right Column: Automated Patching Tools & Pinouts
        right_panel = ctk.CTkFrame(self, fg_color=("gray90", "gray14"), corner_radius=8)
        right_panel.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=5)
        right_panel.grid_columnconfigure(0, weight=1)

        scroll_tools = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
        scroll_tools.pack(fill="both", expand=True, padx=4, pady=4)
        scroll_tools.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(scroll_tools, text="🛠️ Herramientas de Parcheo Automático", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=6, pady=(4, 6))

        # 1. Unlock Rosewood Terminal
        btn_unlock = ctk.CTkButton(
            scroll_tools,
            text="🔓 Desbloquear Terminal F3 (Rosewood Bypass)",
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._cmd_patch_unlock
        )
        btn_unlock.pack(fill="x", padx=6, pady=4)

        # 2. Modify Serial Number
        sn_card = ctk.CTkFrame(scroll_tools, fg_color=("gray85", "gray20"), corner_radius=6)
        sn_card.pack(fill="x", padx=6, pady=6)
        sn_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(sn_card, text="Editar Número de Serie (8 chars):", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(6, 2))
        self.txt_new_sn = ctk.CTkEntry(sn_card, placeholder_text="Ej: WAAAAAAA")
        self.txt_new_sn.grid(row=1, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")

        btn_sn = ctk.CTkButton(sn_card, text="Modificar", width=80, command=self._cmd_modify_sn)
        btn_sn.grid(row=1, column=1, padx=(4, 8), pady=(0, 6))

        # 3. CH341A / CH340 Pinout Reference Card
        pin_card = ctk.CTkFrame(scroll_tools, fg_color=("#1e293b", "#0f172a"), corner_radius=6)
        pin_card.pack(fill="x", padx=6, pady=(10, 6))
        
        ctk.CTkLabel(pin_card, text="📌 Pinout Programador CH341A -> Winbond 25Q80", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(8, 2))
        
        pin_text = (
            "CH341A (Slot SPI 25xx):\n"
            "• Pin 1: /CS (Cable Rojo / Pinza 1)\n"
            "• Pin 2: DO (MISO / Data Out)\n"
            "• Pin 3: /WP (Write Protect)\n"
            "• Pin 4: GND (Tierra)\n"
            "• Pin 5: DI (MOSI / Data In)\n"
            "• Pin 6: CLK (Señal de Reloj)\n"
            "• Pin 7: /HOLD\n"
            "• Pin 8: VCC (3.3V)\n\n"
            "⚠️ Nunca alimentes a 5V; el chip 25Q80 se dañará permanentemente."
        )
        ctk.CTkLabel(pin_card, text=pin_text, font=("Consolas", 10), justify="left", text_color="#cbd5e1").pack(anchor="w", padx=8, pady=(0, 8))

    def _cmd_open_rom(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar volcado de ROM Flash",
            filetypes=[("Archivos de ROM / Binarios", "*.bin;*.rom;*.dat;*.bin8"), ("Todos los archivos", "*.*")]
        )
        if not filepath:
            return

        try:
            self.patcher = SPIROMPatcher.load_from_file(filepath)
            self.current_filepath = filepath
            self.current_offset = 0
            self.btn_save.configure(state="normal")
            
            # Analyze metadata
            inspector = Winbond25Q80ROMInspector.from_file(filepath)
            res = inspector.analyze()

            filename = os.path.basename(filepath)
            self.lbl_file_info.configure(
                text=f"{filename} ({res.get('size_str')}) | {res.get('vendor_type')} | SN: {res.get('serial')}",
                text_color="#38bdf8"
            )
            self._render_hex_view()
            self._log(f"ROM cargada en el Editor: {filename} ({res.get('size_str')})")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la ROM: {e}")

    def _cmd_save_rom(self):
        if not self.patcher:
            return
        save_path = filedialog.asksaveasfilename(
            title="Guardar archivo ROM modificado para CH341A",
            defaultextension=".bin",
            filetypes=[("Archivo Binario ROM", "*.bin"), ("Archivo ROM", "*.rom"), ("Todos los archivos", "*.*")],
            initialfile=f"PATCHED_{os.path.basename(self.current_filepath or 'rom.bin')}"
        )
        if save_path:
            try:
                self.patcher.save_to_file(save_path)
                messagebox.showinfo("Guardado Exitoso", f"ROM guardada exitosamente en:\n{save_path}\n\nLista para ser flasheada con CH341A / NeoProgrammer.")
                self._log(f"ROM guardada exitosamente: {save_path}")
            except Exception as e:
                messagebox.showerror("Error al Guardar", f"No se pudo guardar la ROM: {e}")

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

        # Check if hex query or ascii
        try:
            if query.startswith("0x") or all(c in "0123456789ABCDEFabcdef " for c in query) and len(query.replace(" ", "")) % 2 == 0:
                pattern = bytes.fromhex(query.replace("0x", "").replace(" ", ""))
            else:
                pattern = query.encode('ascii')
        except ValueError:
            pattern = query.encode('ascii', errors='ignore')

        matches = self.patcher.search_pattern(pattern, start_offset=self.current_offset + 1)
        if not matches:
            # Wrap around search from 0
            matches = self.patcher.search_pattern(pattern, start_offset=0)

        if matches:
            found_offset = matches[0]
            self.current_offset = (found_offset // 16) * 16
            self._render_hex_view()
            self._log(f"Patrón encontrado en offset: 0x{found_offset:06X}")
        else:
            messagebox.showinfo("Búsqueda", f"No se encontró el patrón '{query}' en la memoria ROM.")

    def _cmd_patch_unlock(self):
        if not self.patcher:
            messagebox.showwarning("Aviso", "Abre primero un archivo de volcado de ROM.")
            return

        res = self.patcher.find_and_patch_seagate_unlock()
        details_str = "\n".join(res.get("details", []))
        messagebox.showinfo("Resultado del Parche", f"Parche de desbloqueo aplicado:\n\n{details_str}\n\nGuarda el archivo y grábalo con tu programador CH341A.")
        self._render_hex_view()
        self._log(f"Parche Rosewood Unlock aplicado: {res.get('patches_applied')} modificaciones.")

    def _cmd_modify_sn(self):
        if not self.patcher:
            return
        new_sn = self.txt_new_sn.get().strip()
        if len(new_sn) != 8:
            messagebox.showerror("Error", "El número de serie debe tener exactamente 8 caracteres alfanuméricos.")
            return

        res = self.patcher.modify_serial_number(new_sn)
        if res.get("success"):
            messagebox.showinfo("Serial Modificado", f"Se actualizó el número de serie a '{new_sn}' en {res.get('replaced_instances')} ubicaciones de la ROM.")
            self._render_hex_view()
            self._log(f"Serial Number modificado en ROM a: {new_sn}")
        else:
            messagebox.showwarning("Aviso", "No se encontró la cadena de número de serie en formato estándar dentro de la ROM.")

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(f"[SPI-EDITOR] {text}")
