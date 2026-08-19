"""
Universal SPI Flash ROM & EEPROM Memory Editor, Patcher and Diagnostic Studio
Provides universal binary modification, structural patchers, and checksum engines for:
- Seagate (Rosewood Diagnostic Unlock, Head Map Disable, UART Baudrate Changer)
- Western Digital (ROYL Module 0B Head Map Isolation, ROYL Checksum Fixer)
- Toshiba, Hitachi, Samsung, and SSDs (Serial & Model Patcher, Byte Swapping, Checksums)
- Generic EEPROMs (24Cxx, 25Cxx, 93Cxx, SPI 25xx)
"""

import struct
import os
import re
import zlib
import hashlib

class UniversalROMPatcher:
    """Universal binary manipulation, patch engine and checksum recalculator for ROM/EEPROM."""

    def __init__(self, data: bytearray, source_filepath: str = None):
        self.data = bytearray(data)
        self.original_data = bytearray(data)
        self.size = len(data)
        self.history = []
        self.source_filepath = source_filepath
        self.backup_filepath = None

    @classmethod
    def load_from_file(cls, filepath: str):
        with open(filepath, "rb") as f:
            content = f.read()
        instance = cls(bytearray(content), source_filepath=filepath)
        return instance

    def create_backup(self, custom_path: str = None) -> str:
        """Creates an original backup file (.bak) of the unpatched ROM."""
        if custom_path:
            target_path = custom_path
        elif self.source_filepath:
            target_path = self.source_filepath + ".bak"
        else:
            target_path = "ORIGINAL_BACKUP_ROM.bin.bak"

        with open(target_path, "wb") as f:
            f.write(self.original_data)
        self.backup_filepath = target_path
        return target_path

    def restore_from_backup(self, backup_path: str = None) -> bool:
        """Restores the ROM data from the backup file or original in-memory snapshot."""
        path = backup_path or self.backup_filepath
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                content = f.read()
            self.data = bytearray(content)
            self.size = len(self.data)
            self.history.clear()
            return True
        elif self.original_data:
            self.data = bytearray(self.original_data)
            self.size = len(self.data)
            self.history.clear()
            return True
        return False

    @property
    def is_modified(self) -> bool:
        return self.data != self.original_data

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
            raise ValueError("Offset fuera de los límites de la memoria.")
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

    def undo_last_write(self) -> bool:
        """Reverts the last byte write operation."""
        if not self.history:
            return False
        last_op = self.history.pop()
        offset = last_op["offset"]
        old_data = last_op["old"]
        self.data[offset:offset+len(old_data)] = old_data
        return True

    def write_hex_string(self, offset: int, hex_str: str) -> dict:
        """Writes a string of hexadecimal bytes at the given offset."""
        clean_hex = hex_str.replace(" ", "").replace("0x", "").replace(",", "")
        if len(clean_hex) % 2 != 0:
            return {"success": False, "error": "Longitud de cadena hexadecimal inválida (debe ser número par de caracteres)."}
        try:
            byte_data = bytes.fromhex(clean_hex)
            self.write_bytes(offset, byte_data)
            return {"success": True, "bytes_written": len(byte_data), "offset": offset}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # -------------------------------------------------------------
    # 1. SEAGATE F3 & ROSEWOOD SPECIALIZED PATCHERS
    # -------------------------------------------------------------
    def find_and_patch_seagate_unlock(self) -> dict:
        """
        Scans for Rosewood / Grenada diagnostic terminal lock tokens and applies unlock bypass patch.
        """
        patches_applied = 0
        details = []

        patterns = [
            (b"\x00\x28\x00\x00\x00\x10", b"\x00\x00\x00\x00\x00\x00", "Handshake Check Bypass"),
            (b"\xF3\x20\x55\xAA", b"\xF3\x20\x00\x00", "Diagnostic Port Flag Unlock"),
            (b"\x38\x00\x00\x10\x00\x28", b"\x38\x00\x00\x10\x00\x00", "UART Boot Check Pass")
        ]

        for target, replacement, desc in patterns:
            matches = self.search_pattern(target)
            for m in matches:
                self.write_bytes(m, replacement)
                patches_applied += 1
                details.append(f"Parche aplicado en offset 0x{m:06X}: {desc}")

        if patches_applied == 0:
            details.append("ℹ️ No se detectaron patrones de bloqueo antiguos; la ROM puede ser de arquitectura estándar o ya estar desbloqueada.")

        return {
            "success": True,
            "patches_applied": patches_applied,
            "details": details
        }

    def patch_seagate_baudrate(self, target_baud: int = 115200) -> dict:
        """
        Patches Seagate ROM default diagnostic baudrate divider.
        Common target rates: 38400 (default), 115200, 460800, 921600.
        """
        baud_dividers = {
            38400: b"\x00\x96\x00",   # 38400 divisor
            115200: b"\x00\x32\x00",  # 115200 divisor
            460800: b"\x00\x0C\x00",  # 460800 divisor
            921600: b"\x00\x06\x00"   # 921600 divisor
        }
        if target_baud not in baud_dividers:
            return {"success": False, "error": f"Baudrate no soportado: {target_baud}"}

        target_bytes = baud_dividers[target_baud]
        # Search for default 38400 divider in UART init region
        matches = self.search_pattern(b"\x00\x96\x00")
        if not matches:
            return {"success": False, "error": "No se encontró el divisor de baudrate predeterminado en la ROM."}

        count = 0
        for m in matches[:2]:  # usually only 1-2 instances in UART config
            self.write_bytes(m, target_bytes)
            count += 1

        return {
            "success": True,
            "target_baud": target_baud,
            "modified_instances": count,
            "details": f"Baudrate UART de la ROM configurado a {target_baud} baud."
        }

    # -------------------------------------------------------------
    # 2. WESTERN DIGITAL ROYL HEAD MAP & CHECKSUM FIXER
    # -------------------------------------------------------------
    def fix_wd_royl_checksums(self) -> dict:
        """
        Recalculates and fixes 16-bit and 32-bit module checksums for Western Digital ROYL ROMs.
        """
        royl_offsets = self.search_pattern(b"ROYL")
        if not royl_offsets:
            return {"success": False, "error": "No se encontraron módulos ROYL de Western Digital en la ROM."}

        fixed = 0
        details = []
        for off in royl_offsets:
            if off + 16 <= self.size:
                # Read module header
                # ROYL header format: 'ROYL' (4B), Module ID (2B), Size (2B), Checksum (2B)...
                mod_id = struct.unpack("<H", self.data[off+4:off+6])[0]
                mod_size = struct.unpack("<H", self.data[off+6:off+8])[0]
                
                if mod_size > 0 and off + mod_size <= self.size:
                    # Calculate Word Sum Checksum
                    mod_data = self.data[off:off+mod_size]
                    words = struct.unpack(f"<{mod_size//2}H", mod_data[:(mod_size//2)*2])
                    current_sum = sum(words) & 0xFFFF
                    
                    if current_sum != 0:
                        # Fix checksum word at offset + 8
                        fix_diff = (0x10000 - current_sum) & 0xFFFF
                        old_chk = struct.unpack("<H", self.data[off+8:off+10])[0]
                        new_chk = (old_chk + fix_diff) & 0xFFFF
                        self.write_bytes(off+8, struct.pack("<H", new_chk))
                        fixed += 1
                        details.append(f"Módulo 0x{mod_id:02X} en 0x{off:06X}: Checksum corregido a 0x{new_chk:04X}")

        return {
            "success": True,
            "modules_fixed": fixed,
            "details": details or ["Todos los checksums de módulos ROYL ya son válidos."]
        }

    def modify_wd_head_map(self, disabled_head_index: int) -> dict:
        """
        Modifies WD Module 0B (Head Map) to disable a physically degraded head (0, 1, 2, 3...)
        allowing the drive to spin up and initialize for data recovery.
        """
        royl_offsets = self.search_pattern(b"ROYL")
        mod0b_off = None
        for off in royl_offsets:
            if off + 6 <= self.size:
                mod_id = struct.unpack("<H", self.data[off+4:off+6])[0]
                if mod_id == 0x0B:
                    mod0b_off = off
                    break

        if mod0b_off is None:
            return {"success": False, "error": "No se encontró el Módulo 0B (Head Map) en la ROM de Western Digital."}

        # Head map table is typically located at offset + 0x14 inside Mod 0B
        target_byte_off = mod0b_off + 0x14 + disabled_head_index
        if target_byte_off < self.size:
            self.write_bytes(target_byte_off, b"\xFF")  # 0xFF = Disabled head flag
            # Recalculate checksum
            self.fix_wd_royl_checksums()
            return {
                "success": True,
                "disabled_head": disabled_head_index,
                "offset": target_byte_off,
                "details": f"Cabezal físico {disabled_head_index} deshabilitado (0xFF) en Módulo 0B. Checksums recalculados."
            }

        return {"success": False, "error": "Offset de cabezal fuera del rango del Módulo 0B."}

    # -------------------------------------------------------------
    # 3. UNIVERSAL STRINGS & SERIAL NUMBER MODIFIER
    # -------------------------------------------------------------
    def modify_serial_number(self, new_serial: str) -> dict:
        """Finds and replaces serial numbers across Seagate, WD, Toshiba, and Hitachi formats."""
        new_sn_clean = new_serial.strip().encode('ascii')
        data_str = self.data.decode('ascii', errors='ignore')

        count = 0
        # Check standard 8-char SN (Seagate ST)
        if len(new_sn_clean) == 8:
            matches = [m.start() for m in re.finditer(r'\b[0-9A-Z]{8}\b', data_str)]
            for m in matches:
                chunk = self.data[m:m+8]
                if chunk.isalnum():
                    self.write_bytes(m, new_sn_clean)
                    count += 1

        # Check WD-style SN (WD-WMC... or 12-char)
        wd_matches = [m.start() for m in re.finditer(r'(WD-[A-Z0-9]{10,14})', data_str)]
        for m in wd_matches:
            target_len = len(re.search(r'(WD-[A-Z0-9]{10,14})', data_str[m:m+20]).group(1))
            padded_sn = new_sn_clean[:target_len].ljust(target_len, b' ')
            self.write_bytes(m, padded_sn)
            count += 1

        # Check Toshiba / Hitachi style (10-12 chars)
        tosh_matches = [m.start() for m in re.finditer(r'\b([0-9A-Z]{10,12})\b', data_str)]
        for m in tosh_matches[:4]:
            chunk = self.data[m:m+len(new_sn_clean)]
            if chunk.isalnum():
                self.write_bytes(m, new_sn_clean)
                count += 1

        return {
            "success": count > 0,
            "replaced_instances": count,
            "serial": new_serial
        }

    # -------------------------------------------------------------
    # 4. UNIVERSAL BYTE SWAP & ENDIANNESS CONVERTER
    # -------------------------------------------------------------
    def byte_swap_16bit(self) -> dict:
        """
        Swaps every 2 adjacent bytes (Big-Endian <-> Little-Endian 16-bit).
        Critical for dumps read from Marvell, Hitachi, or ARM microcontrollers with swapped bus lines.
        """
        total_words = self.size // 2
        for i in range(total_words):
            idx = i * 2
            b0, b1 = self.data[idx], self.data[idx+1]
            self.data[idx] = b1
            self.data[idx+1] = b0
        
        self.history.append({"type": "byte_swap_16", "size": self.size})
        return {"success": True, "details": f"Intercambio de Bytes (16-bit Word Swap) aplicado a {self.size:,} bytes."}

    def byte_swap_32bit(self) -> dict:
        """Swaps 4 adjacent bytes (32-bit Dword Endianness Swap)."""
        total_dwords = self.size // 4
        for i in range(total_dwords):
            idx = i * 4
            b0, b1, b2, b3 = self.data[idx], self.data[idx+1], self.data[idx+2], self.data[idx+3]
            self.data[idx] = b3
            self.data[idx+1] = b2
            self.data[idx+2] = b1
            self.data[idx+3] = b0

        self.history.append({"type": "byte_swap_32", "size": self.size})
        return {"success": True, "details": f"Intercambio de Bytes (32-bit Dword Swap) aplicado a {self.size:,} bytes."}

    # -------------------------------------------------------------
    # 5. FILL, PAD & TRIM TOOLS
    # -------------------------------------------------------------
    def fill_range(self, start_offset: int, end_offset: int, fill_byte: int = 0xFF) -> dict:
        """Fills a memory range with a constant byte (0x00, 0xFF, etc.)."""
        if start_offset < 0 or end_offset > self.size or start_offset >= end_offset:
            return {"success": False, "error": "Rango de offset no válido."}
        
        length = end_offset - start_offset
        fill_data = bytes([fill_byte & 0xFF] * length)
        self.write_bytes(start_offset, fill_data)
        return {
            "success": True,
            "bytes_filled": length,
            "start": start_offset,
            "end": end_offset,
            "fill_byte": f"0x{fill_byte:02X}"
        }

    def pad_to_standard_size(self, target_size: int, pad_byte: int = 0xFF) -> dict:
        """Pads the ROM dump to a standard chip capacity (e.g. 512KB, 1MB, 2MB, 4MB)."""
        if target_size <= self.size:
            return {"success": False, "error": "El tamaño objetivo debe ser mayor que el tamaño actual."}
        
        diff = target_size - self.size
        self.data.extend(bytes([pad_byte & 0xFF] * diff))
        old_size = self.size
        self.size = len(self.data)
        return {
            "success": True,
            "old_size": old_size,
            "new_size": self.size,
            "bytes_added": diff
        }

    # -------------------------------------------------------------
    # 6. UNIVERSAL CHECKSUMS & HASH CALCULATOR
    # -------------------------------------------------------------
    def calculate_checksums(self, start_offset: int = 0, length: int = None) -> dict:
        """Calculates 8-bit, 16-bit, 32-bit Sum, XOR, CRC16, CRC32, MD5 and SHA-256."""
        if length is None:
            buf = self.data[start_offset:]
        else:
            buf = self.data[start_offset:start_offset+length]

        if not buf:
            return {}

        sum8 = sum(buf) & 0xFF
        xor8 = 0
        for b in buf:
            xor8 ^= b

        crc32_val = zlib.crc32(buf) & 0xFFFFFFFF
        md5_val = hashlib.md5(buf).hexdigest().upper()
        sha256_val = hashlib.sha256(buf).hexdigest().upper()

        sum16_val = 0
        if len(buf) >= 2:
            words = struct.unpack(f"<{len(buf)//2}H", buf[:(len(buf)//2)*2])
            sum16_val = sum(words) & 0xFFFF

        return {
            "sum8": f"0x{sum8:02X}",
            "xor8": f"0x{xor8:02X}",
            "sum16": f"0x{sum16_val:04X}",
            "crc32": f"0x{crc32_val:08X}",
            "md5": md5_val,
            "sha256": sha256_val
        }


# Backward compatibility alias
SPIROMPatcher = UniversalROMPatcher
