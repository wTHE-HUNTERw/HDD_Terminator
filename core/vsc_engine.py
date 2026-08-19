"""
VSC (Vendor Specific Commands) & Advanced SMART Reset Engine
Implements vendor-specific protocol sequences for ALL major HDD manufacturers:
  - Western Digital (Marvell / ROYL Architecture)
  - Seagate (Barracuda / Rosewood / Pharaoh / F3)
  - Samsung (SpinPoint Legacy)
  - Toshiba (MQ / DT Series)
  - Hitachi / HGST (Ultrastar / Deskstar)
  - Maxtor (Legacy, inherited by Seagate)
  - Universal ATA Sanitize & Security Erase
"""

from .spti import SPTIController

# Brand detection keywords for auto-classification from ATA IDENTIFY model strings
BRAND_KEYWORDS = {
    "western_digital": ["WDC", "WD", "Western Digital", "WDCWD", "WD Blue", "WD Black", "WD Red", "WD Purple", "WD Gold", "WD Green"],
    "seagate": ["Seagate", "ST", "Barracuda", "IronWolf", "SkyHawk", "Exos", "FireCuda", "Rosewood", "Grenada", "Pharaoh"],
    "samsung": ["Samsung", "SAMSUNG", "SpinPoint", "HD103", "HD502", "HD154", "HD204"],
    "toshiba": ["TOSHIBA", "Toshiba", "MQ01", "MQ04", "DT01", "DT02", "MG0", "MG08", "HDWD", "MK"],
    "hitachi": ["Hitachi", "HITACHI", "HGST", "HTS", "HDS", "HDN", "HUH", "Ultrastar", "Deskstar", "Travelstar", "IC35"],
    "maxtor": ["Maxtor", "MAXTOR", "DiamondMax", "MaXLine", "Atlas"],
}


def detect_brand(model_string: str) -> str:
    """
    Auto-detects the hard drive manufacturer from the ATA IDENTIFY model string.
    Returns: 'western_digital', 'seagate', 'samsung', 'toshiba', 'hitachi', 'maxtor', or 'unknown'
    """
    if not model_string:
        return "unknown"
    model_upper = model_string.upper()
    for brand, keywords in BRAND_KEYWORDS.items():
        for kw in keywords:
            if kw.upper() in model_upper:
                return brand
    return "unknown"


class VSCEngine:
    def __init__(self, drive_path: str):
        self.drive_path = drive_path
        self.controller = SPTIController(drive_path)

    # =============================================================
    # WESTERN DIGITAL VSC (SUPERON & SERVICE AREA MODULES)
    # =============================================================
    def wd_superon_unlock(self) -> dict:
        """
        Sends the Western Digital ATA SuperOn unlock sequence (Opcode 0x80 or 0x45445742).
        Enables access to Service Area (SA) modules.
        """
        with self.controller as spt:
            # WD SuperOn Key: 0x45 0x44 0x57 0x42 ("EDWB")
            res = spt.execute_sat_ata_command(
                command=0x80,
                features=0x02,
                sector_count=0x01,
                lba=0x44574245,
                device=0x00,
                data_direction="none"
            )
        return res

    def wd_read_module(self, module_id: int, num_sectors: int = 1) -> dict:
        """
        Reads a WD Service Area module via VSC Read Module (0xD5).
        Returns the raw module data for backup/analysis before clearing.
        
        :param module_id: Module ID (e.g. 0x21 = SMART, 0x32 = G-List, 0x33 = Translator, 0x47 = Head Map)
        :param num_sectors: Number of 512-byte sectors to read
        """
        buf = bytearray(num_sectors * 512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD5,  # VSC Read Module
                features=num_sectors,  # Length in sectors
                sector_count=module_id,  # Module ID
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="in"
            )
        return res

    def wd_write_module(self, module_id: int, data: bytearray = None, num_sectors: int = 1) -> dict:
        """
        Writes data to a WD Service Area module via VSC Write Module (0xD6).
        If data is None, writes zeros (clearing the module).
        
        :param module_id: Module ID to write
        :param data: Data to write (None = zeros)
        :param num_sectors: Number of sectors
        """
        if data is None:
            data = bytearray(num_sectors * 512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD6,  # VSC Write Module
                features=num_sectors,  # Length in sectors
                sector_count=module_id,  # Module ID
                lba=0x00,
                device=0x00,
                data_buffer=data,
                data_direction="out"
            )
        return res

    def wd_clear_smart_module(self) -> dict:
        """Clears WD SMART Module (0x21) by writing a zeroed module block."""
        return self.wd_write_module(module_id=0x21, num_sectors=1)

    def wd_clear_glist_module(self) -> dict:
        """Clears WD G-List Module (0x32) by writing a zeroed defect table."""
        return self.wd_write_module(module_id=0x32, num_sectors=1)

    def wd_clear_translator_module(self) -> dict:
        """
        Clears WD Translator Module (0x33) by writing zeros.
        This forces the firmware to regenerate the LBA-to-physical translation table
        on next power cycle, effectively re-mapping the disk ignoring old G-List entries.
        """
        return self.wd_write_module(module_id=0x33, num_sectors=1)

    def wd_clear_head_map_module(self) -> dict:
        """
        Clears WD Head Map Module (0x47) by writing zeros.
        Used to reset disabled/degraded head flags in multi-platter drives.
        WARNING: Only use if heads are physically functional; clearing on a drive
        with dead heads will cause firmware errors.
        """
        return self.wd_write_module(module_id=0x47, num_sectors=1)

    def wd_full_reset_sequence(self) -> list:
        """
        Executes the complete WD SMART + Defect reset sequence:
        1. SuperOn Unlock
        2. Backup SMART module (0x21) — read before clear
        3. Clear SMART module (0x21)
        4. Clear G-List module (0x32)
        
        Returns a list of step results for UI reporting.
        """
        results = []
        
        # Step 1: SuperOn Unlock
        res = self.wd_superon_unlock()
        results.append({"step": "SuperOn Unlock (0x80)", "result": res})
        
        # Step 2: Backup SMART module
        res = self.wd_read_module(module_id=0x21)
        results.append({"step": "Backup SMART Module (0x21)", "result": res})
        
        # Step 3: Clear SMART module
        res = self.wd_clear_smart_module()
        results.append({"step": "Clear SMART Module (0x21)", "result": res})
        
        # Step 4: Clear G-List module
        res = self.wd_clear_glist_module()
        results.append({"step": "Clear G-List Module (0x32)", "result": res})
        
        return results

    def wd_read_rom(self, num_sectors: int = 2048) -> dict:
        """
        Reads the full SPI Flash ROM directly from the WD drive over SATA/USB via VSC (0xD5).
        Default 2048 sectors = 1 MB (Winbond/Macronix/GigaDevice).
        """
        self.wd_superon_unlock()
        buf = bytearray(num_sectors * 512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD5,  # VSC Read Module/ROM
                features=min(num_sectors, 256),  # Chunk size
                sector_count=0x00,  # Module 0x00 / ROM direct
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="in"
            )
        res["rom_data"] = buf
        return res

    def wd_write_rom(self, rom_data: bytearray) -> dict:
        """
        Writes and flashes the modified ROM data directly to the WD drive over SATA/USB via VSC (0xD6).
        """
        self.wd_superon_unlock()
        num_sectors = max(1, len(rom_data) // 512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD6,  # VSC Write Module/ROM
                features=min(num_sectors, 256),
                sector_count=0x00,  # Module 0x00 / ROM direct
                lba=0x00,
                device=0x00,
                data_buffer=rom_data,
                data_direction="out"
            )
        return res

    def wd_backup_module_to_file(self, module_id: int, filepath: str, num_sectors: int = 1) -> dict:
        """Reads a module and saves it to a backup .bin file."""
        res = self.wd_read_module(module_id=module_id, num_sectors=num_sectors)
        if res.get("success") and res.get("data"):
            with open(filepath, "wb") as f:
                f.write(res["data"])
            return {"success": True, "filepath": filepath, "bytes": len(res["data"])}
        return {"success": False, "error": res.get("error", "Error al leer módulo.")}

    def wd_restore_module_from_file(self, module_id: int, filepath: str) -> dict:
        """Reads a .bin file and writes it back to the drive module."""
        if not os.path.exists(filepath):
            return {"success": False, "error": f"Archivo de backup no encontrado: {filepath}"}
        with open(filepath, "rb") as f:
            data = f.read()
        num_sectors = max(1, len(data) // 512)
        return self.wd_write_module(module_id=module_id, data=bytearray(data), num_sectors=num_sectors)

    # =============================================================
    # SEAGATE VSC (DIRECT ATA — NO SERIAL TERMINAL REQUIRED)
    # =============================================================
    def seagate_vsc_enter_diagnostic(self) -> dict:
        """
        Sends Seagate Diagnostic Mode VSC (Opcode 0x3B, Features 0xCC).
        Enables vendor-specific diagnostic command set on Seagate drives.
        Compatible with Barracuda 7200.11, 7200.12, and some Rosewood models.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0xCC,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def seagate_vsc_clear_smart(self) -> dict:
        """
        Clears Seagate SMART data via VSC (Opcode 0x3B, Features 0x10, SC=0x01).
        Sends the vendor clear-SMART-log command that resets attribute counters.
        Requires diagnostic mode to be active first.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x10,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def seagate_vsc_clear_glist(self) -> dict:
        """
        Clears Seagate G-List (Grown Defect List) via VSC.
        Opcode 0x3B, Features 0x11, SC=0x01.
        Removes all entries from the grown defect list.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x11,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def seagate_vsc_clear_plist(self) -> dict:
        """
        Clears Seagate P-List (Primary/Factory Defect List) via VSC.
        Opcode 0x3B, Features 0x12, SC=0x01.
        WARNING: Clearing the P-List is rarely needed and can cause issues
        if factory defects are no longer tracked.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x12,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def seagate_vsc_regenerate_translator(self) -> dict:
        """
        Forces Seagate translator regeneration via VSC.
        Opcode 0x3B, Features 0x20.
        Rebuilds the LBA-to-physical mapping table.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x20,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def seagate_full_reset_sequence(self) -> list:
        """
        Executes the complete Seagate VSC SMART + Defect reset sequence via ATA:
        1. Enter Diagnostic Mode
        2. Clear SMART Logs
        3. Clear G-List
        4. Regenerate Translator
        """
        results = []
        
        res = self.seagate_vsc_enter_diagnostic()
        results.append({"step": "Enter Diagnostic Mode (0x3B/0xCC)", "result": res})
        
        res = self.seagate_vsc_clear_smart()
        results.append({"step": "Clear SMART Data", "result": res})
        
        res = self.seagate_vsc_clear_glist()
        results.append({"step": "Clear G-List", "result": res})
        
        res = self.seagate_vsc_regenerate_translator()
        results.append({"step": "Regenerate Translator", "result": res})
        
        return results

    # =============================================================
    # SAMSUNG VSC
    # =============================================================
    def samsung_vsc_enter_sa(self) -> dict:
        """Sends Samsung VSC to enter Service Area (Opcode 0xDF, Features 0x01)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xDF,
                features=0x01,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def samsung_vsc_clear_smart(self) -> dict:
        """Sends Samsung VSC to clear SMART logs and defect lists (Opcode 0xE0 / 0xE4)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xE0,
                features=0x01,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def samsung_vsc_clear_glist(self) -> dict:
        """Sends Samsung VSC to clear G-List / Defect Table (Opcode 0xE4)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xE4,
                features=0x01,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def samsung_full_reset_sequence(self) -> list:
        """
        Executes the complete Samsung VSC SMART reset sequence:
        1. Enter Service Area
        2. Clear SMART Logs
        3. Clear G-List
        """
        results = []
        
        res = self.samsung_vsc_enter_sa()
        results.append({"step": "Enter Service Area (0xDF)", "result": res})
        
        res = self.samsung_vsc_clear_smart()
        results.append({"step": "Clear SMART Logs (0xE0)", "result": res})
        
        res = self.samsung_vsc_clear_glist()
        results.append({"step": "Clear G-List (0xE4)", "result": res})
        
        return results

    # =============================================================
    # TOSHIBA VSC (DIRECT ATA COMMANDS)
    # =============================================================
    def toshiba_vsc_enter_service_mode(self) -> dict:
        """
        Sends Toshiba VSC to enter Service/Diagnostic mode.
        Opcode 0xFE, Features 0x01.
        Enables access to vendor-specific commands on Toshiba MQ/DT series.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFE,
                features=0x01,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def toshiba_vsc_clear_smart(self) -> dict:
        """
        Clears Toshiba SMART attribute counters via VSC.
        Opcode 0xFE, Features 0x10.
        Resets reallocated sectors count and pending sectors.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFE,
                features=0x10,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def toshiba_vsc_clear_glist(self) -> dict:
        """
        Clears Toshiba G-List (Grown Defect List) via VSC.
        Opcode 0xFE, Features 0x11.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFE,
                features=0x11,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def toshiba_vsc_regenerate_translator(self) -> dict:
        """
        Forces Toshiba translator table regeneration via VSC.
        Opcode 0xFE, Features 0x20.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFE,
                features=0x20,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def toshiba_full_reset_sequence(self) -> list:
        """
        Executes the complete Toshiba VSC SMART reset sequence:
        1. Enter Service Mode
        2. Clear SMART Data
        3. Clear G-List
        4. Regenerate Translator
        """
        results = []
        
        res = self.toshiba_vsc_enter_service_mode()
        results.append({"step": "Enter Service Mode (0xFE)", "result": res})
        
        res = self.toshiba_vsc_clear_smart()
        results.append({"step": "Clear SMART Data", "result": res})
        
        res = self.toshiba_vsc_clear_glist()
        results.append({"step": "Clear G-List", "result": res})
        
        res = self.toshiba_vsc_regenerate_translator()
        results.append({"step": "Regenerate Translator", "result": res})
        
        return results

    # =============================================================
    # HITACHI / HGST VSC
    # =============================================================
    def hitachi_vsc_enter_service_mode(self) -> dict:
        """
        Sends Hitachi/HGST VSC to enter Diagnostic/Service mode.
        Opcode 0xFC, Features 0x01.
        Enables access to NV-RAM SMART operations on Ultrastar/Deskstar/Travelstar.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFC,
                features=0x01,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def hitachi_vsc_clear_smart_nvram(self) -> dict:
        """
        Clears Hitachi/HGST NV-RAM SMART data via VSC.
        Opcode 0xFC, Features 0x10.
        Resets non-volatile SMART attribute storage.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFC,
                features=0x10,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def hitachi_vsc_clear_glist(self) -> dict:
        """
        Clears Hitachi/HGST G-List via VSC.
        Opcode 0xFC, Features 0x11.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFC,
                features=0x11,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def hitachi_vsc_clear_error_logs(self) -> dict:
        """
        Clears Hitachi/HGST internal error logs via VSC.
        Opcode 0xFC, Features 0x12.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xFC,
                features=0x12,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def hitachi_full_reset_sequence(self) -> list:
        """
        Executes the complete Hitachi/HGST VSC SMART reset sequence:
        1. Enter Service Mode
        2. Clear NV-RAM SMART
        3. Clear G-List
        4. Clear Error Logs
        """
        results = []
        
        res = self.hitachi_vsc_enter_service_mode()
        results.append({"step": "Enter Service Mode (0xFC)", "result": res})
        
        res = self.hitachi_vsc_clear_smart_nvram()
        results.append({"step": "Clear NV-RAM SMART", "result": res})
        
        res = self.hitachi_vsc_clear_glist()
        results.append({"step": "Clear G-List", "result": res})
        
        res = self.hitachi_vsc_clear_error_logs()
        results.append({"step": "Clear Error Logs", "result": res})
        
        return results

    # =============================================================
    # MAXTOR VSC (LEGACY — INHERITED BY SEAGATE)
    # =============================================================
    def maxtor_vsc_enter_diagnostic(self) -> dict:
        """
        Sends Maxtor Diagnostic Mode VSC.
        Maxtor drives (DiamondMax, MaXLine, Atlas) use Opcode 0x3B similar to Seagate.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0xCC,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def maxtor_vsc_clear_smart(self) -> dict:
        """Clears Maxtor SMART data via VSC (same opcode family as Seagate)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x10,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def maxtor_vsc_clear_glist(self) -> dict:
        """Clears Maxtor G-List via VSC."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0x3B,
                features=0x11,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    def maxtor_full_reset_sequence(self) -> list:
        """
        Executes the complete Maxtor VSC SMART reset sequence:
        1. Enter Diagnostic Mode
        2. Clear SMART Data
        3. Clear G-List
        """
        results = []
        
        res = self.maxtor_vsc_enter_diagnostic()
        results.append({"step": "Enter Diagnostic Mode (0x3B/0xCC)", "result": res})
        
        res = self.maxtor_vsc_clear_smart()
        results.append({"step": "Clear SMART Data", "result": res})
        
        res = self.maxtor_vsc_clear_glist()
        results.append({"step": "Clear G-List", "result": res})
        
        return results

    # =============================================================
    # ATA SANITIZE DEVICE & SECURITY ERASE (UNIVERSAL)
    # =============================================================
    def ata_sanitize_device(self, mode: str = "crypto") -> dict:
        """
        Executes ATA SANITIZE DEVICE (0xB4).
        Mode: 'crypto' (Crypto Scramble 0x0011), 'overwrite' (0x0014), 'status' (0x0000)
        Forces drive controller to flush and reinitialize defect and security tables.
        """
        mode_map = {
            "status": 0x0000,
            "crypto": 0x0011,
            "overwrite": 0x0014,
            "exit": 0x0020
        }
        feat = mode_map.get(mode.lower(), 0x0011)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xB4,  # ATA SANITIZE DEVICE
                features=feat,
                sector_count=0x00,
                lba=0x44617461,  # Key pattern
                device=0x00,
                data_direction="none"
            )
        return res

    def ata_sanitize_status(self) -> dict:
        """
        Polls ATA SANITIZE DEVICE status (0xB4, Features 0x0000).
        Returns current sanitize operation progress.
        """
        return self.ata_sanitize_device(mode="status")

    def ata_security_set_password(self, password: str = "Terminator123") -> dict:
        """Executes ATA SECURITY SET PASSWORD (0xF1)."""
        # Password sector: 2 bytes identifier (0 = User), 32 bytes password, padded with 0
        buf = bytearray(512)
        buf[0] = 0x00  # User password
        pass_bytes = password.encode('ascii')[:32]
        buf[2:2+len(pass_bytes)] = pass_bytes
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xF1,
                features=0x00,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="out"
            )
        return res

    def ata_security_erase(self, enhanced: bool = True, password: str = "Terminator123") -> dict:
        """
        Executes ATA SECURITY ERASE (0xF4).
        Enhanced Erase writes vendor-specific patterns on all sectors, forcing the firmware
        to clear pending bad sectors (ID 197) and retest defect candidates.
        """
        buf = bytearray(512)
        buf[0] = 0x01 if enhanced else 0x00  # 1 = Enhanced Erase
        pass_bytes = password.encode('ascii')[:32]
        buf[2:2+len(pass_bytes)] = pass_bytes
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xF4,
                features=0x00,
                sector_count=0x01,
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="out"
            )
        return res

    def ata_security_unlock(self, password: str = "Terminator123", master: bool = False) -> dict:
        """
        Executes ATA SECURITY UNLOCK (0xF2).
        Unlocks a drive that has been locked with ATA Security Set Password.
        
        :param password: The password to unlock with (max 32 ASCII chars)
        :param master: If True, use Master password; if False, use User password
        """
        buf = bytearray(512)
        buf[0] = 0x01 if master else 0x00
        pass_bytes = password.encode('ascii')[:32]
        buf[2:2+len(pass_bytes)] = pass_bytes
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xF2,
                features=0x00,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="out"
            )
        return res

    def ata_security_disable_password(self, password: str = "Terminator123", master: bool = False) -> dict:
        """
        Executes ATA SECURITY DISABLE PASSWORD (0xF6).
        Removes the ATA password lock from the drive.
        The drive must be unlocked first with ata_security_unlock().
        """
        buf = bytearray(512)
        buf[0] = 0x01 if master else 0x00
        pass_bytes = password.encode('ascii')[:32]
        buf[2:2+len(pass_bytes)] = pass_bytes
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xF6,
                features=0x00,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_buffer=buf,
                data_direction="out"
            )
        return res

    def ata_security_freeze_lock(self) -> dict:
        """
        Executes ATA SECURITY FREEZE LOCK (0xF5).
        Prevents any further security commands until next power cycle.
        Useful as a safety measure after operations.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xF5,
                features=0x00,
                sector_count=0x00,
                lba=0x00,
                device=0x00,
                data_direction="none"
            )
        return res

    # =============================================================
    # UNIVERSAL 1-CLICK RESET DISPATCHER
    # =============================================================
    def execute_full_reset_by_brand(self, brand: str) -> list:
        """
        Dispatches the appropriate full SMART + defect reset sequence 
        based on the detected brand.
        
        :param brand: One of 'western_digital', 'seagate', 'samsung', 'toshiba', 'hitachi', 'maxtor'
        :returns: List of step results
        """
        dispatch = {
            "western_digital": self.wd_full_reset_sequence,
            "seagate": self.seagate_full_reset_sequence,
            "samsung": self.samsung_full_reset_sequence,
            "toshiba": self.toshiba_full_reset_sequence,
            "hitachi": self.hitachi_full_reset_sequence,
            "maxtor": self.maxtor_full_reset_sequence,
        }
        handler = dispatch.get(brand)
        if handler:
            return handler()
        else:
            return [{"step": "Error", "result": {"success": False, "error": f"Marca no soportada para reset automático: {brand}"}}]
