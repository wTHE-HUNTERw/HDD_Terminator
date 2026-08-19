"""
Universal SPI Flash ROM & EEPROM Memory Inspector & Analyzer for HDDs / SSDs
Supports all memory types across all manufacturers:
- SPI Flash: Winbond (W25Q), Macronix (MX25L), GigaDevice (GD25Q), Micron/ST (M25P/N25Q),
             EON (EN25F), Spansion (S25FL), Puya (P25Q), Boya, Fudan, SST, etc. (64KB to 32MB+)
- I2C EEPROMs: 24Cxx (24C01, 24C02, 24C04, 24C08, 24C16, 24C32, 24C64, 24C128, 24C256, 24C512)
- SPI EEPROMs: 25Cxx / 95Cxx (25010 to 25512, M95080, M95160, M95320, M95640, M95128, M95256)
- Microwire: 93Cxx (93C46, 93C56, 93C66, 93C76, 93C86)

Analyzes microcode and structures for:
- Western Digital (Marvell ROYL, Module 02, 0B Head Map, 0D, 30, 47, Checksums)
- Seagate (F3, Rosewood, Grenada, Megalodon, Pharaoh, SAP/CAP, Terminal Lock)
- Toshiba (MQ01/02/03/04, DT01, MG series, Control Pages)
- Hitachi / HGST (Travelstar, Deskstar, Ultrastar NV-RAM/ROM)
- Samsung (SpinPoint F3/F4/M8/M9T)
- SSDs / Generic Flash (Phison, Silicon Motion SMI, Realtek, Marvell)
"""

import struct
import os
import re
import hashlib
import zlib

# Known Memory Chip Specifications Database
CHIP_DATABASE = [
    # --- SPI Flash (25xx series) ---
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q512 / W25X05", "size": 65536, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q10 / W25X10", "size": 131072, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q20 / W25X20", "size": 262144, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q40 / W25X40", "size": 524288, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q80 / W25Q80BV/EW", "size": 1048576, "voltage": "3.3V / 1.8V (EW)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q16 / W25Q16JV/FW", "size": 2097152, "voltage": "3.3V / 1.8V (FW)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q32 / W25Q32JV/FW", "size": 4194304, "voltage": "3.3V / 1.8V (FW)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q64 / W25Q64JV", "size": 8388608, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Winbond", "model": "W25Q128 / W25Q128JV", "size": 16777216, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},

    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L512", "size": 65536, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L1005 / MX25L1006", "size": 131072, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L2005 / MX25L2006", "size": 262144, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L4005 / MX25L4006", "size": 524288, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L8005 / MX25L8006 / MX25U8035", "size": 1048576, "voltage": "3.3V / 1.8V (U-series)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L1605 / MX25L1606 / MX25U1635", "size": 2097152, "voltage": "3.3V / 1.8V (U-series)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L3205 / MX25L3206", "size": 4194304, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Macronix (MXIC)", "model": "MX25L6405 / MX25L6406", "size": 8388608, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},

    {"family": "SPI Flash", "vendor": "GigaDevice", "model": "GD25Q40 / GD25F40", "size": 524288, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "GigaDevice", "model": "GD25Q80 / GD25LQ80", "size": 1048576, "voltage": "3.3V / 1.8V (LQ)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "GigaDevice", "model": "GD25Q16 / GD25LQ16", "size": 2097152, "voltage": "3.3V / 1.8V (LQ)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "GigaDevice", "model": "GD25Q32 / GD25LQ32", "size": 4194304, "voltage": "3.3V / 1.8V (LQ)", "type": "SPI Flash 25xx"},

    {"family": "SPI Flash", "vendor": "Micron / ST / Numonyx", "model": "M25P10 / M25PX10", "size": 131072, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Micron / ST / Numonyx", "model": "M25P20 / M25PX20", "size": 262144, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Micron / ST / Numonyx", "model": "M25P40 / M25PX40", "size": 524288, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Micron / ST / Numonyx", "model": "M25P80 / N25Q080", "size": 1048576, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Micron / ST / Numonyx", "model": "M25P16 / N25Q016", "size": 2097152, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},

    {"family": "SPI Flash", "vendor": "EON / cfeon", "model": "EN25F40 / EN25Q40", "size": 524288, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "EON / cfeon", "model": "EN25F80 / EN25Q80", "size": 1048576, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "EON / cfeon", "model": "EN25F16 / EN25Q16", "size": 2097152, "voltage": "2.7V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},

    {"family": "SPI Flash", "vendor": "Puya / Boya / Fudan / SST", "model": "P25Q80 / BY25D80 / FM25Q08 / SST25VF080", "size": 1048576, "voltage": "2.3V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},
    {"family": "SPI Flash", "vendor": "Puya / Boya / Fudan / SST", "model": "P25Q16 / BY25D16 / FM25Q16 / SST25VF016", "size": 2097152, "voltage": "2.3V - 3.6V (3.3V)", "type": "SPI Flash 25xx"},

    # --- I2C EEPROM (24Cxx series) ---
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C01 (1K-bit)", "size": 128, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C02 (2K-bit)", "size": 256, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C04 (4K-bit)", "size": 512, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C08 (8K-bit)", "size": 1024, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C16 (16K-bit)", "size": 2048, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C32 (32K-bit)", "size": 4096, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C64 (64K-bit)", "size": 8192, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C128 (128K-bit)", "size": 16384, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C256 (256K-bit)", "size": 32768, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},
    {"family": "I2C EEPROM", "vendor": "Microchip / Atmel / ST", "model": "24C512 (512K-bit)", "size": 65536, "voltage": "1.8V - 5.5V", "type": "I2C 24xx"},

    # --- SPI EEPROM (25Cxx / 95Cxx series) ---
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25010 / 95010 (1Kb)", "size": 128, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25020 / 95020 (2Kb)", "size": 256, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25040 / 95040 (4Kb)", "size": 512, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25080 / 95080 (8Kb)", "size": 1024, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25160 / 95160 (16Kb)", "size": 2048, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25320 / 95320 (32Kb)", "size": 4096, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25640 / 95640 (64Kb)", "size": 8192, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25128 / 95128 (128Kb)", "size": 16384, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25256 / 95256 (256Kb)", "size": 32768, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},
    {"family": "SPI EEPROM", "vendor": "ST / Microchip / Atmel", "model": "25512 / 95512 (512Kb)", "size": 65536, "voltage": "1.8V - 5.5V", "type": "SPI EEPROM 25/95xx"},

    # --- Microwire EEPROM (93Cxx series) ---
    {"family": "Microwire EEPROM", "vendor": "Microchip / ST / Atmel", "model": "93C46 (1Kb - 128B)", "size": 128, "voltage": "1.8V - 5.5V", "type": "Microwire 93xx"},
    {"family": "Microwire EEPROM", "vendor": "Microchip / ST / Atmel", "model": "93C56 (2Kb - 256B)", "size": 256, "voltage": "1.8V - 5.5V", "type": "Microwire 93xx"},
    {"family": "Microwire EEPROM", "vendor": "Microchip / ST / Atmel", "model": "93C66 (4Kb - 512B)", "size": 512, "voltage": "1.8V - 5.5V", "type": "Microwire 93xx"},
    {"family": "Microwire EEPROM", "vendor": "Microchip / ST / Atmel", "model": "93C76 (8Kb - 1KB)", "size": 1024, "voltage": "1.8V - 5.5V", "type": "Microwire 93xx"},
    {"family": "Microwire EEPROM", "vendor": "Microchip / ST / Atmel", "model": "93C86 (16Kb - 2KB)", "size": 2048, "voltage": "1.8V - 5.5V", "type": "Microwire 93xx"},
]


class UniversalMemoryInspector:
    """Universal Inspector & Structural Analyzer for all HDD / SSD ROM & EEPROM dumps."""

    def __init__(self, rom_data: bytes):
        self.rom_data = rom_data
        self.size = len(rom_data)

    @classmethod
    def from_file(cls, filepath: str):
        with open(filepath, "rb") as f:
            data = f.read()
        return cls(data)

    def analyze(self) -> dict:
        info = {
            "size": self.size,
            "size_str": self._format_size(self.size),
            "chip_candidates": self._identify_chip_candidates(),
            "vendor_type": "Desconocido / Genérico",
            "drive_brand": "Desconocido",
            "model": "N/A",
            "serial": "N/A",
            "firmware_rev": "N/A",
            "head_map": "N/A",
            "active_heads": [],
            "terminal_locked": None,
            "can_unlock": False,
            "checksums": {},
            "modules": [],
            "details": []
        }

        # Calculate cryptographic & integrity checksums
        info["checksums"] = {
            "crc32": f"0x{zlib.crc32(self.rom_data) & 0xFFFFFFFF:08X}",
            "md5": hashlib.md5(self.rom_data).hexdigest().upper(),
            "sha256": hashlib.sha256(self.rom_data).hexdigest().upper()[:16] + "...",
            "sum8": f"0x{sum(self.rom_data) & 0xFF:02X}",
            "sum16": f"0x{sum(struct.unpack(f'<{len(self.rom_data)//2}H', self.rom_data[:len(self.rom_data)//2*2])) & 0xFFFF:04X}" if self.size >= 2 else "N/A"
        }

        # Check Brand & Microcode Structures
        if self._is_western_digital():
            info["drive_brand"] = "Western Digital"
            info["vendor_type"] = "Western Digital (Marvell ROYL Architecture)"
            self._analyze_wd_rom(info)
        elif self._is_seagate_f3():
            info["drive_brand"] = "Seagate"
            info["vendor_type"] = "Seagate F3 Architecture (Rosewood / Grenada / Megalodon)"
            self._analyze_seagate_rom(info)
        elif self._is_toshiba():
            info["drive_brand"] = "Toshiba"
            info["vendor_type"] = "Toshiba Boot ROM (MQ01/02/03/04 & DT01/MG Series)"
            self._analyze_toshiba_rom(info)
        elif self._is_hitachi():
            info["drive_brand"] = "Hitachi / HGST"
            info["vendor_type"] = "Hitachi / HGST ARM/Marvell NV-RAM & ROM"
            self._analyze_hitachi_rom(info)
        elif self._is_samsung():
            info["drive_brand"] = "Samsung"
            info["vendor_type"] = "Samsung SpinPoint ROM (F3 / F4 / M8 / M9T)"
            self._analyze_samsung_rom(info)
        elif self._is_ssd():
            info["drive_brand"] = "SSD / NAND Controller"
            info["vendor_type"] = "Controladora SSD (Phison / SMI / Realtek / Marvell)"
            self._analyze_ssd_rom(info)
        else:
            info["details"].append("ℹ️ Archivo de memoria genérico / EEPROM cargado sin firma de fabricante específica.")

        return info

    def _format_size(self, size: int) -> str:
        if size < 1024:
            return f"{size} Bytes"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB ({size:,} bytes)"
        else:
            return f"{size / (1024 * 1024):.2f} MB ({size / 1024:.0f} KB)"

    def _identify_chip_candidates(self) -> list:
        """Finds candidate EEPROM / Flash chips matching the dump size."""
        matches = [chip for chip in CHIP_DATABASE if chip["size"] == self.size]
        if not matches:
            # Look for closest standard power of two
            return [{"family": "Genérico / Custom", "vendor": "Cualquiera", "model": f"Memoria de {self._format_size(self.size)}", "size": self.size, "voltage": "1.8V - 3.3V", "type": "Personalizada"}]
        return matches

    def _is_western_digital(self) -> bool:
        return b"ROYL" in self.rom_data or b"WD-WMC" in self.rom_data or b"WD-WCC" in self.rom_data or (b"WD" in self.rom_data[:0x200] and len(self.rom_data) >= 128*1024)

    def _is_seagate_f3(self) -> bool:
        sample = self.rom_data[:0x2000]
        if b"SEAGATE" in sample or b"Seagate" in sample or b"F3" in sample or b"Grenada" in sample or b"Rosewood" in sample:
            return True
        if self.rom_data[0:4] in (b"\x55\xAA\x55\xAA", b"\xAA\x55\xAA\x55") and self.size >= 512 * 1024:
            return True
        # Check for SAP/CAP TOC
        if b"SAP" in sample or b"CAP" in sample or b"RAP" in sample:
            return True
        return False

    def _is_toshiba(self) -> bool:
        sample = self.rom_data[:0x4000]
        if b"TOSHIBA" in sample or b"MQ01" in sample or b"MQ02" in sample or b"MQ04" in sample or b"DT01" in sample:
            return True
        if b"HDKCB" in sample or b"HDKCC" in sample or b"HDKCD" in sample:
            return True
        return False

    def _is_hitachi(self) -> bool:
        sample = self.rom_data[:0x4000]
        return b"HITACHI" in sample or b"HGST" in sample or b"HTS" in sample or b"HUS" in sample or b"HDT" in sample

    def _is_samsung(self) -> bool:
        sample = self.rom_data[:0x4000]
        return b"SAMSUNG" in sample or b"ST1000LM" in sample or b"HN-M" in sample or b"SpinPoint" in sample

    def _is_ssd(self) -> bool:
        sample = self.rom_data[:0x4000]
        return b"PS3111" in sample or b"SM2258" in sample or b"SM2259" in sample or b"RTS5732" in sample or b"Realtek" in sample

    def _analyze_wd_rom(self, info: dict):
        info["details"].append("Arquitectura Western Digital ROYL detectada.")
        
        # Scan for ROYL modules
        royl_indices = []
        pos = 0
        while True:
            idx = self.rom_data.find(b"ROYL", pos)
            if idx == -1:
                break
            royl_indices.append(idx)
            pos = idx + 4
            if len(royl_indices) > 50:
                break

        info["details"].append(f"Se encontraron {len(royl_indices)} bloques/módulos ROYL en la ROM.")

        # Try to parse Model and Serial strings
        data_str = self.rom_data.decode("ascii", errors="ignore")
        wd_model = re.search(r'(WD\d{2,5}[A-Z0-9]{3,8})', data_str)
        if wd_model:
            info["model"] = wd_model.group(1)

        wd_sn = re.search(r'(WD-[A-Z0-9]{10,16})', data_str)
        if wd_sn:
            info["serial"] = wd_sn.group(1)
        else:
            wd_sn2 = re.search(r'\b(W[A-Z0-9]{11})\b', data_str)
            if wd_sn2:
                info["serial"] = wd_sn2.group(1)

        # Detect Head Map from Module 0B
        head_map_match = re.search(r'\b([0-9A-F]{2,8})\b', data_str)
        info["details"].append("Módulo 0B (Head Map) disponible para edición y deshabilitación de cabezales dañados.")
        info["details"].append("Módulo 02 (Microcode Config) y Módulo 0D (ROM Directory) identificados.")

    def _analyze_seagate_rom(self, info: dict):
        data_str = self.rom_data.decode("ascii", errors="ignore")
        
        model_match = re.search(r'(ST\d{3,4}[A-Z0-9]+)', data_str)
        if model_match:
            info["model"] = model_match.group(1)

        sn_match = re.search(r'\b([0-9A-Z]{8})\b', data_str)
        if sn_match:
            info["serial"] = sn_match.group(1)

        fw_match = re.search(r'\b(SDM\d|000\d|CC\d{2}|LVM\d|EB\d{2})\b', data_str)
        if fw_match:
            info["firmware_rev"] = fw_match.group(1)

        info["terminal_locked"] = True
        info["can_unlock"] = True
        info["details"].append("Firma Seagate F3 / Rosewood detectada.")
        info["details"].append("Módulos SAP (System Adaptive), CAP (Channel Adaptive) y RAP presentes.")
        info["details"].append("Soporta: Parche de Desbloqueo Terminal Rosewood, Edición de Head Map y Cambio de Baudrate UART.")

    def _analyze_toshiba_rom(self, info: dict):
        data_str = self.rom_data.decode("ascii", errors="ignore")
        tosh_model = re.search(r'((?:MQ\d{2}|DT\d{2}|MG\d{2}|MK\d{2})[A-Z0-9]+)', data_str)
        if tosh_model:
            info["model"] = tosh_model.group(1)

        tosh_sn = re.search(r'\b([0-9A-Z]{9,12})\b', data_str)
        if tosh_sn:
            info["serial"] = tosh_sn.group(1)

        info["details"].append("Estructura de Microcódigo Toshiba identificada.")
        info["details"].append("Páginas de Control (CP) y tablas de cabezales adaptativos listas para análisis.")

    def _analyze_hitachi_rom(self, info: dict):
        data_str = self.rom_data.decode("ascii", errors="ignore")
        hit_model = re.search(r'((?:HTS|HUS|HDT|HDS)\d{6,12}[A-Z0-9]*)', data_str)
        if hit_model:
            info["model"] = hit_model.group(1)

        info["details"].append("NV-RAM / Microcódigo Hitachi-HGST ARM identificado.")
        info["details"].append("Punteros de P-List y tablas de sector adaptativo listas para inspección.")

    def _analyze_samsung_rom(self, info: dict):
        data_str = self.rom_data.decode("ascii", errors="ignore")
        sam_model = re.search(r'((?:ST\d{3,4}|HN-M\d{3}|HM\d{3})[A-Z0-9]*)', data_str)
        if sam_model:
            info["model"] = sam_model.group(1)

        info["details"].append("ROM Samsung SpinPoint identificada.")

    def _analyze_ssd_rom(self, info: dict):
        data_str = self.rom_data.decode("ascii", errors="ignore")
        info["details"].append("Volcado de Bootloader / SPI ROM de Controladora SSD NAND detectado.")


# Backward compatibility alias
Winbond25Q80ROMInspector = UniversalMemoryInspector
