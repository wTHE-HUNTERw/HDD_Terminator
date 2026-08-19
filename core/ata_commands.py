"""
ATA Command Suite & Parser
Implements standard ATA-8 ACS commands, decoders for IDENTIFY DEVICE, SMART data/attributes, and raw sector operations.
"""

import struct
from .spti import SPTIController

# Standard ATA Opcodes
ATA_NOP = 0x00
ATA_IDENTIFY_DEVICE = 0xEC
ATA_IDENTIFY_PACKET_DEVICE = 0xA1
ATA_SMART = 0xB0
ATA_READ_SECTORS = 0x20
ATA_READ_SECTORS_EXT = 0x24
ATA_WRITE_SECTORS = 0x30
ATA_WRITE_SECTORS_EXT = 0x34
ATA_CHECK_POWER_MODE = 0xE5
ATA_STANDBY_IMMEDIATE = 0xE0
ATA_IDLE_IMMEDIATE = 0xE1
ATA_SLEEP = 0xE6
ATA_READ_NATIVE_MAX_ADDRESS = 0xF8
ATA_SECURITY_UNLOCK = 0xF2
ATA_SECURITY_DISABLE_PASSWORD = 0xF6

# SMART Subcommands (passed in Features register)
SMART_READ_DATA = 0xD0
SMART_READ_ATTRIBUTES_THRESHOLD = 0xD1
SMART_ENABLE_DISABLE_AUTOSAVE = 0xD2
SMART_EXECUTE_OFFLINE_IMMEDIATE = 0xD4
SMART_READ_LOG = 0xD5
SMART_WRITE_LOG = 0xD6
SMART_ENABLE_OPERATIONS = 0xD8
SMART_DISABLE_OPERATIONS = 0xD9
SMART_RETURN_STATUS = 0xDA

# Known SMART Attribute Dictionary
SMART_ATTRIBUTE_NAMES = {
    1: "Raw Read Error Rate",
    2: "Throughput Performance",
    3: "Spin-Up Time",
    4: "Start/Stop Count",
    5: "Reallocated Sectors Count",
    7: "Seek Error Rate",
    8: "Seek Time Performance",
    9: "Power-On Hours (POH)",
    10: "Spin Retry Count",
    11: "Calibration Retry Count",
    12: "Power Cycle Count",
    13: "Soft Read Error Rate",
    184: "End-to-End Error / IOEDC",
    187: "Reported Uncorrectable Errors",
    188: "Command Timeout",
    189: "High Fly Writes",
    190: "Airflow Temperature",
    191: "G-Sense / Shock Error Rate",
    192: "Power-Off Retract Count",
    193: "Load/Unload Cycle Count",
    194: "Temperature (Celsius)",
    195: "Hardware ECC Recovered",
    196: "Reallocation Event Count",
    197: "Current Pending Sector Count",
    198: "Offline Uncorrectable Sector Count",
    199: "UltraDMA CRC Error Count",
    200: "Multi-Zone Error Rate",
    220: "Disk Shift",
    240: "Head Flying Hours",
    241: "Total LBAs Written",
    242: "Total LBAs Read",
}

def swap_bytes_string(byte_array: bytes) -> str:
    """ATA stores strings with adjacent bytes swapped."""
    res = bytearray()
    for i in range(0, len(byte_array) - 1, 2):
        res.append(byte_array[i + 1])
        res.append(byte_array[i])
    if len(byte_array) % 2 != 0:
        res.append(byte_array[-1])
    return res.decode("ascii", errors="replace").strip()

class ATACommandExecutor:
    def __init__(self, drive_path: str):
        self.drive_path = drive_path
        self.controller = SPTIController(drive_path)

    def identify_device(self) -> dict:
        """Executes ATA IDENTIFY DEVICE (0xEC) and parses key device parameters."""
        buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_IDENTIFY_DEVICE,
                features=0,
                sector_count=1,
                lba=0,
                device=0,
                data_buffer=buf,
                data_direction="in",
                is_lba48=False
            )
        
        raw_data = res.get("data")
        if not raw_data or len(raw_data) < 512:
            return {"success": False, "error": "No se recibieron datos de IDENTIFY DEVICE", "raw_result": res}

        # Parse ATA IDENTIFY 512-byte block
        # Words 10-19: Serial Number (20 chars)
        serial = swap_bytes_string(raw_data[20:40])
        # Words 23-26: Firmware Revision (8 chars)
        firmware = swap_bytes_string(raw_data[46:54])
        # Words 27-46: Model Number (40 chars)
        model = swap_bytes_string(raw_data[54:94])
        
        # Word 60-61: Total sectors in 28-bit LBA mode
        lba28_sectors = struct.unpack_from("<I", raw_data, 120)[0]
        # Word 100-103: Total sectors in 48-bit LBA mode
        lba48_sectors = struct.unpack_from("<Q", raw_data, 200)[0]
        
        total_sectors = lba48_sectors if lba48_sectors > 0 else lba28_sectors
        capacity_gb = (total_sectors * 512) / (1024 ** 3)
        
        # Word 82/83/84: Command sets supported
        cmd_set_82 = struct.unpack_from("<H", raw_data, 164)[0]
        cmd_set_83 = struct.unpack_from("<H", raw_data, 166)[0]
        smart_supported = bool(cmd_set_82 & 0x0001)
        security_supported = bool(cmd_set_82 & 0x0002)
        lba48_supported = bool(cmd_set_83 & 0x0400)
        
        # Word 85/86/87: Command sets enabled
        cmd_set_85 = struct.unpack_from("<H", raw_data, 170)[0]
        smart_enabled = bool(cmd_set_85 & 0x0001)
        
        # Word 128: Security Status
        sec_status = struct.unpack_from("<H", raw_data, 256)[0]
        sec_enabled = bool(sec_status & 0x0002)
        sec_locked = bool(sec_status & 0x0004)
        sec_frozen = bool(sec_status & 0x0008)

        # Word 217: Nominal Media Rotation Rate (RPM)
        rpm = struct.unpack_from("<H", raw_data, 434)[0]
        rpm_str = "SSD / Non-rotating" if rpm == 1 else (f"{rpm} RPM" if rpm > 1 else "Desconocido")

        return {
            "success": True,
            "model": model,
            "serial": serial,
            "firmware": firmware,
            "total_sectors": total_sectors,
            "capacity_gb": capacity_gb,
            "smart_supported": smart_supported,
            "smart_enabled": smart_enabled,
            "security_supported": security_supported,
            "security_locked": sec_locked,
            "security_frozen": sec_frozen,
            "lba48_supported": lba48_supported,
            "rpm": rpm_str,
            "raw_data": raw_data,
            "raw_result": res
        }

    def read_smart_data(self) -> dict:
        """Executes ATA SMART READ DATA (0xB0, Features 0xD0, LBA Mid 0x4F, LBA High 0xC2) and parses attributes."""
        buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_READ_DATA,
                sector_count=1,
                lba=(0xC2 << 16) | (0x4F << 8), # LBA Mid 0x4F, LBA High 0xC2
                device=0,
                data_buffer=buf,
                data_direction="in",
                is_lba48=False
            )
        
        raw_data = res.get("data")
        if not raw_data or len(raw_data) < 512:
            return {"success": False, "error": "No se pudo leer la tabla SMART. El dispositivo o case USB puede requerir habilitar SMART o no soporta SAT SMART.", "raw_result": res}

        # Parse SMART Attributes: 30 entries of 12 bytes each, starting at offset 2
        attributes = []
        for i in range(30):
            offset = 2 + (i * 12)
            attr_id = raw_data[offset]
            if attr_id == 0:
                continue
            
            flags = struct.unpack_from("<H", raw_data, offset + 1)[0]
            curr_val = raw_data[offset + 3]
            worst_val = raw_data[offset + 4]
            raw_bytes = raw_data[offset + 5: offset + 11]
            raw_val = int.from_bytes(raw_bytes, byteorder="little")
            
            attr_name = SMART_ATTRIBUTE_NAMES.get(attr_id, f"Vendor Specific ({attr_id})")
            
            # Formatted raw value for common attributes
            raw_str = str(raw_val)
            if attr_id in (194, 190):  # Temperature
                temp = raw_bytes[0]
                raw_str = f"{temp} °C"
            elif attr_id == 9: # Power on hours
                raw_str = f"{raw_val} horas ({raw_val/24:.1f} días)"
                
            attributes.append({
                "id": attr_id,
                "name": attr_name,
                "current": curr_val,
                "worst": worst_val,
                "raw": raw_val,
                "raw_str": raw_str,
                "pre_failure": bool(flags & 0x0001)
            })

        return {
            "success": True,
            "attributes": attributes,
            "raw_data": raw_data,
            "raw_result": res
        }

    def check_smart_status(self) -> dict:
        """Executes ATA SMART RETURN STATUS (0xB0, Features 0xDA)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_RETURN_STATUS,
                sector_count=0,
                lba=(0xC2 << 16) | (0x4F << 8),
                device=0,
                data_buffer=None,
                data_direction="none"
            )
        regs = res.get("ata_registers", {})
        lba_val = regs.get("lba", 0)
        lba_mid = (lba_val >> 8) & 0xFF
        lba_high = (lba_val >> 16) & 0xFF
        
        # SMART Threshold Exceeded condition: LBA Mid = 0xF4, LBA High = 0x2C
        # Good status: LBA Mid = 0x4F, LBA High = 0xC2
        threshold_exceeded = (lba_mid == 0xF4 and lba_high == 0x2C)
        return {
            "success": res.get("success", False),
            "threshold_exceeded": threshold_exceeded,
            "status_str": "FALLO INMINENTE / THRESHOLD EXCEEDED" if threshold_exceeded else "SALUD OK / NORMAL",
            "registers": regs,
            "raw_result": res
        }

    def smart_enable(self) -> dict:
        """Executes ATA SMART ENABLE OPERATIONS (0xB0, Features 0xD8, LBA Mid 0x4F, LBA High 0xC2)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_ENABLE_OPERATIONS,
                sector_count=0,
                lba=(0xC2 << 16) | (0x4F << 8),
                device=0,
                data_direction="none"
            )
        return res

    def smart_disable(self) -> dict:
        """Executes ATA SMART DISABLE OPERATIONS (0xB0, Features 0xD9, LBA Mid 0x4F, LBA High 0xC2)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_DISABLE_OPERATIONS,
                sector_count=0,
                lba=(0xC2 << 16) | (0x4F << 8),
                device=0,
                data_direction="none"
            )
        return res

    def smart_autosave(self, enable: bool = True) -> dict:
        """Executes ATA SMART ENABLE/DISABLE ATTRIBUTE AUTOSAVE (0xB0, Features 0xD2)."""
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_ENABLE_DISABLE_AUTOSAVE,
                sector_count=0xF1 if enable else 0x00,
                lba=(0xC2 << 16) | (0x4F << 8),
                device=0,
                data_direction="none"
            )
        return res

    def smart_self_test(self, test_type: str = "short") -> dict:
        """
        Executes SMART EXECUTE OFFLINE IMMEDIATE / SELF TEST (0xB0, Features 0xD4).
        test_type options: 'offline', 'short', 'extended', 'conveyance', 'abort'
        """
        type_map = {
            "offline": 0x00,
            "short": 0x01,
            "extended": 0x02,
            "conveyance": 0x03,
            "abort": 0x7F
        }
        lba_low = type_map.get(test_type.lower(), 0x01)
        lba_val = (0xC2 << 16) | (0x4F << 8) | lba_low
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_EXECUTE_OFFLINE_IMMEDIATE,
                sector_count=0,
                lba=lba_val,
                device=0,
                data_direction="none"
            )
        return res

    def smart_read_log(self, log_address: int, page_count: int = 1) -> dict:
        """Executes ATA SMART READ LOG (0xB0, Features 0xD5, LBA Low = Log Address)."""
        buf = bytearray(page_count * 512)
        lba_val = (0xC2 << 16) | (0x4F << 8) | (log_address & 0xFF)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_READ_LOG,
                sector_count=page_count,
                lba=lba_val,
                device=0,
                data_buffer=buf,
                data_direction="in"
            )
        return res

    def read_sector(self, lba: int) -> dict:
        """Reads 1 sector (512 bytes) from the given LBA address."""
        buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_READ_SECTORS_EXT if lba > 0x0FFFFFFF else ATA_READ_SECTORS,
                features=0,
                sector_count=1,
                lba=lba,
                device=0x40 if lba > 0x0FFFFFFF else 0x00,
                data_buffer=buf,
                data_direction="in",
                is_lba48=(lba > 0x0FFFFFFF)
            )
        return {
            "success": res.get("success", False),
            "lba": lba,
            "data": res.get("data"),
            "raw_result": res
        }

    def power_command(self, action: str) -> dict:
        """Sends ATA power management commands: 'standby', 'sleep', 'idle', 'check'."""
        cmd_map = {
            "standby": ATA_STANDBY_IMMEDIATE,
            "sleep": ATA_SLEEP,
            "idle": ATA_IDLE_IMMEDIATE,
            "check": ATA_CHECK_POWER_MODE
        }
        cmd = cmd_map.get(action.lower(), ATA_CHECK_POWER_MODE)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=cmd,
                features=0,
                sector_count=0,
                lba=0,
                device=0,
                data_direction="none"
            )
        return res

    def execute_raw_command(
        self,
        command: int,
        features: int = 0,
        sector_count: int = 0,
        lba: int = 0,
        device: int = 0,
        buffer_size: int = 0,
        direction: str = "none",
        is_lba48: bool = False
    ) -> dict:
        """Executes an arbitrary ATA command with custom register values."""
        buf = bytearray(buffer_size) if buffer_size > 0 else None
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=command,
                features=features,
                sector_count=sector_count,
                lba=lba,
                device=device,
                data_buffer=buf,
                data_direction=direction,
                is_lba48=is_lba48
            )
        return res

    def read_smart_thresholds(self) -> dict:
        """
        Executes ATA SMART READ ATTRIBUTE THRESHOLDS (0xB0, Features 0xD1).
        Returns threshold values for each SMART attribute ID.
        """
        buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_SMART,
                features=SMART_READ_ATTRIBUTES_THRESHOLD,
                sector_count=1,
                lba=(0xC2 << 16) | (0x4F << 8),
                device=0,
                data_buffer=buf,
                data_direction="in",
                is_lba48=False
            )

        raw_data = res.get("data")
        if not raw_data or len(raw_data) < 512:
            return {"success": False, "error": "No se pudo leer la tabla de umbrales SMART.", "raw_result": res}

        thresholds = {}
        for i in range(30):
            offset = 2 + (i * 12)
            attr_id = raw_data[offset]
            if attr_id == 0:
                continue
            threshold_val = raw_data[offset + 1]
            thresholds[attr_id] = threshold_val

        return {
            "success": True,
            "thresholds": thresholds,
            "raw_data": raw_data,
            "raw_result": res
        }

    def read_smart_selftest_log(self) -> dict:
        """
        Reads SMART Self-Test Results Log (Log Address 0x06).
        Parses the 21 self-test entries showing test type, status, lifetime hours, and failing LBA.
        """
        log_res = self.smart_read_log(log_address=0x06, page_count=1)
        raw_data = log_res.get("data")
        if not raw_data or len(raw_data) < 512:
            return {"success": False, "error": "No se pudo leer el log de Self-Test (0x06).", "raw_result": log_res}

        # Parse self-test log structure
        # Byte 0: Self-test log data structure revision (should be 0x01)
        revision = raw_data[0]
        # Byte 1: Self-test log index (pointer to most recent entry, 1-based, 0 = no entries)
        log_index = raw_data[1]

        entries = []
        # 21 entries of 24 bytes each, starting at offset 2
        for i in range(21):
            offset = 2 + (i * 24)
            if offset + 24 > len(raw_data):
                break

            test_num = raw_data[offset]  # Test number (descriptor index)
            status_byte = raw_data[offset + 1]
            test_type_nibble = (status_byte >> 4) & 0x0F
            test_status_nibble = status_byte & 0x0F

            # Remaining lifetime hours when test was run
            lifetime_hours = struct.unpack_from("<H", raw_data, offset + 2)[0]
            # Failing LBA (if applicable)
            failing_lba = struct.unpack_from("<I", raw_data, offset + 4)[0]

            if test_num == 0 and status_byte == 0 and lifetime_hours == 0:
                continue  # Empty entry

            # Decode test type
            test_type_names = {
                0x00: "Offline",
                0x01: "Short (Offline)",
                0x02: "Extended (Offline)",
                0x03: "Conveyance",
                0x04: "Selective",
                0x81: "Short (Captive)",
                0x82: "Extended (Captive)",
            }
            test_type_str = test_type_names.get(test_type_nibble, f"Desconocido (0x{test_type_nibble:02X})")

            # Decode test status
            status_names = {
                0x00: "Completado sin errores",
                0x01: "Abortado por el host",
                0x02: "Interrumpido por reset",
                0x03: "Error fatal / No se pudo completar",
                0x04: "Tipo de test desconocido",
                0x05: "Error eléctrico",
                0x06: "Error de servo",
                0x07: "Error de lectura",
                0x08: "Error por daño manejado",
                0x0F: "En progreso",
            }
            status_str = status_names.get(test_status_nibble, f"Desconocido (0x{test_status_nibble:X})")

            entries.append({
                "test_num": test_num,
                "test_type": test_type_str,
                "status": status_str,
                "status_code": test_status_nibble,
                "lifetime_hours": lifetime_hours,
                "failing_lba": failing_lba if test_status_nibble not in (0x00, 0x01, 0x0F) else None,
            })

        return {
            "success": True,
            "revision": revision,
            "log_index": log_index,
            "entries": entries,
            "raw_data": raw_data,
            "raw_result": log_res
        }

    def read_native_max_address(self) -> dict:
        """
        Executes ATA READ NATIVE MAX ADDRESS (0xF8).
        Returns the true native capacity of the drive, which may differ from the
        user-accessible capacity if a Host Protected Area (HPA) or DCO is active.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_READ_NATIVE_MAX_ADDRESS,
                features=0,
                sector_count=0,
                lba=0,
                device=0x40,  # LBA mode
                data_direction="none"
            )

        regs = res.get("ata_registers", {})
        native_lba = regs.get("lba", 0)
        native_sectors = native_lba + 1 if native_lba > 0 else 0
        native_gb = (native_sectors * 512) / (1024 ** 3) if native_sectors > 0 else 0

        return {
            "success": res.get("success", False),
            "native_max_lba": native_lba,
            "native_sectors": native_sectors,
            "native_capacity_gb": native_gb,
            "registers": regs,
            "raw_result": res
        }

    def write_sector(self, lba: int, data: bytes) -> dict:
        """
        Writes 1 sector (512 bytes) to the given LBA address.
        WARNING: This is a destructive operation that overwrites data on disk.
        
        :param lba: Target LBA address
        :param data: Exactly 512 bytes to write
        """
        if len(data) != 512:
            return {"success": False, "error": f"El buffer de escritura debe ser de 512 bytes, se proporcionaron {len(data)}."}

        buf = bytearray(data)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_WRITE_SECTORS_EXT if lba > 0x0FFFFFFF else ATA_WRITE_SECTORS,
                features=0,
                sector_count=1,
                lba=lba,
                device=0x40 if lba > 0x0FFFFFFF else 0x00,
                data_buffer=buf,
                data_direction="out",
                is_lba48=(lba > 0x0FFFFFFF)
            )
        return {
            "success": res.get("success", False),
            "lba": lba,
            "raw_result": res
        }

    def check_power_mode(self) -> dict:
        """
        Executes ATA CHECK POWER MODE (0xE5).
        Returns the current power mode of the drive via the Sector Count register.
        Values: 0x00 = Standby, 0x40 = NV Cache Spindown, 0x41 = NV Cache Spinup,
                0x80 = Idle, 0xFF = Active/Idle.
        """
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=ATA_CHECK_POWER_MODE,
                features=0,
                sector_count=0,
                lba=0,
                device=0,
                data_direction="none"
            )

        regs = res.get("ata_registers", {})
        sc = regs.get("sector_count", 0)
        mode_map = {
            0x00: "Standby",
            0x40: "NV Cache Spindown",
            0x41: "NV Cache Spinup",
            0x80: "Idle",
            0xFF: "Active / Idle",
        }
        mode_str = mode_map.get(sc, f"Desconocido (0x{sc:02X})")

        return {
            "success": res.get("success", False),
            "power_mode": mode_str,
            "sector_count_raw": sc,
            "registers": regs,
            "raw_result": res
        }

    def export_smart_report(self) -> dict:
        """
        Generates a comprehensive SMART diagnostic report combining:
        - IDENTIFY data
        - SMART attributes with thresholds
        - SMART health status
        - Self-test history
        Returns a dict with all data suitable for CSV/JSON/TXT export.
        """
        report = {"success": True, "sections": {}}

        # 1. IDENTIFY
        try:
            ident = self.identify_device()
            report["sections"]["identify"] = ident
        except Exception as e:
            report["sections"]["identify"] = {"success": False, "error": str(e)}

        # 2. SMART Attributes
        try:
            smart = self.read_smart_data()
            report["sections"]["smart_attributes"] = smart
        except Exception as e:
            report["sections"]["smart_attributes"] = {"success": False, "error": str(e)}

        # 3. SMART Thresholds
        try:
            thresh = self.read_smart_thresholds()
            report["sections"]["smart_thresholds"] = thresh
        except Exception as e:
            report["sections"]["smart_thresholds"] = {"success": False, "error": str(e)}

        # 4. SMART Status
        try:
            status = self.check_smart_status()
            report["sections"]["smart_status"] = status
        except Exception as e:
            report["sections"]["smart_status"] = {"success": False, "error": str(e)}

        # 5. Self-Test Log
        try:
            selftest = self.read_smart_selftest_log()
            report["sections"]["selftest_log"] = selftest
        except Exception as e:
            report["sections"]["selftest_log"] = {"success": False, "error": str(e)}

        # 6. Power Mode
        try:
            power = self.check_power_mode()
            report["sections"]["power_mode"] = power
        except Exception as e:
            report["sections"]["power_mode"] = {"success": False, "error": str(e)}

        return report
