"""
Interactive SPI Flash ROM Editor & Firmware Patcher
Supports Winbond W25Q80 (1MB), W25Q16 (2MB), W25Q32, and CH341A / CH340 ROM dumps.
"""

import struct
import os
import re

class SPIROMPatcher:
    def __init__(self, data: bytearray):
        self.data = bytearray(data)
        self.size = len(data)
        self.history = []

    @classmethod
    def load_from_file(cls, filepath: str):
        with open(filepath, "rb") as f:
            content = f.read()
        return cls(bytearray(content))

    def save_to_file(self, filepath: str):
        with open(filepath, "wb") as f:
            f.write(self.data)

    def get_chunk(self, offset: int, length: int = 512) -> bytes:
        if offset < 0 or offset >= self.size:
            return b""
        end = min(self.size, offset + length)
        return bytes(self.data[offset:end])

    def write_bytes(self, offset: int, new_bytes: bytes):
        if offset < 0 or offset + len(new_bytes) > self.size:
            raise ValueError("Offset fuera de los límites de la memoria ROM.")
        old_data = bytes(self.data[offset:offset+len(new_bytes)])
        self.data[offset:offset+len(new_bytes)] = new_bytes
        self.history.append({"offset": offset, "old": old_data, "new": new_bytes})

    def search_pattern(self, pattern: bytes, start_offset: int = 0) -> list:
        results = []
        pos = start_offset
        while True:
            idx = self.data.find(pattern, pos)
            if idx == -1:
                break
            results.append(idx)
            pos = idx + 1
            if len(results) >= 100:
                break
        return results

    def find_and_patch_seagate_unlock(self) -> dict:
        """
        Scans for Rosewood / Grenada diagnostic terminal lock tokens and applies unlock patch.
        """
        # Common Seagate Diagnostic Lock Signatures (jump/branch check on diag UART)
        # e.g., 0x28 0x00 ... -> NOP / Bypass branch
        patches_applied = 0
        details = []

        # Signature 1: Rosewood handshake bypass pattern
        patterns = [
            (b"\x00\x28\x00\x00\x00\x10", b"\x00\x00\x00\x00\x00\x00", "Handshake Check Bypass"),
            (b"\xF3\x20\x55\xAA", b"\xF3\x20\x00\x00", "Diagnostic Port Flag Unlock")
        ]

        for target, replacement, desc in patterns:
            matches = self.search_pattern(target)
            for m in matches:
                self.write_bytes(m, replacement)
                patches_applied += 1
                details.append(f"Parche aplicado en offset 0x{m:06X}: {desc}")

        if patches_applied == 0:
            # Check generic marker or apply header bypass
            details.append("ℹ️ No se detectaron patrones de bloqueo antiguos; la ROM puede ser de arquitectura estándar o ya estar desbloqueada.")

        return {
            "success": True,
            "patches_applied": patches_applied,
            "details": details
        }

    def modify_serial_number(self, new_serial: str) -> dict:
        """Finds and replaces 8-character Seagate serial number."""
        new_sn_bytes = new_serial.strip().encode('ascii')[:8].ljust(8, b' ')
        data_str = self.data.decode('ascii', errors='ignore')
        matches = [m.start() for m in re.finditer(r'\b[0-9A-Z]{8}\b', data_str)]
        
        count = 0
        for m in matches:
            # Avoid overwriting ASCII instructions
            chunk = self.data[m:m+8]
            if chunk.isalnum():
                self.write_bytes(m, new_sn_bytes)
                count += 1

        return {"success": count > 0, "replaced_instances": count}
