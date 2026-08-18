"""
Hex Dump Viewer Component for CustomTkinter
Renders binary buffers in a formatted hex & ascii grid.
"""

import customtkinter as ctk

class HexViewFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.text_box = ctk.CTkTextbox(
            self,
            font=("Consolas", 12),
            wrap="none",
            activate_scrollbars=True
        )
        self.text_box.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.set_empty_text("No hay datos en el buffer.")

    def set_empty_text(self, msg: str = "Buffer vacío."):
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", f"--- {msg} ---")
        self.text_box.configure(state="disabled")

    def display_data(self, data: bytes, base_offset: int = 0):
        if not data:
            self.set_empty_text("Buffer recibido con 0 bytes.")
            return

        lines = []
        header = f"{'OFFSET':<8}  {'00 01 02 03 04 05 06 07':<23}  {'08 09 0A 0B 0C 0D 0E 0F':<23}  |ASCII|"
        sep = "-" * len(header)
        lines.append(header)
        lines.append(sep)

        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            offset_str = f"{base_offset + i:08X}"
            
            hex_part1 = " ".join(f"{b:02X}" for b in chunk[:8])
            hex_part2 = " ".join(f"{b:02X}" for b in chunk[8:])
            
            ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
            
            line = f"{offset_str}  {hex_part1:<23}  {hex_part2:<23}  |{ascii_part}|"
            lines.append(line)

        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", "end")
        self.text_box.insert("1.0", "\n".join(lines))
        self.text_box.configure(state="disabled")
