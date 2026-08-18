"""
VSC (Vendor Specific Commands) & Advanced SMART Reset Engine
Implements vendor-specific protocol sequences for Western Digital, Seagate, Samsung and ATA Sanitize/Security.
"""

from .spti import SPTIController

class VSCEngine:
    def __init__(self, drive_path: str):
        self.drive_path = drive_path
        self.controller = SPTIController(drive_path)

    # -------------------------------------------------------------
    # WESTERN DIGITAL VSC (SUPERON & SERVICE AREA MODULES)
    # -------------------------------------------------------------
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

    def wd_clear_smart_module(self) -> dict:
        """
        Clears WD SMART Module (0x21) by writing a zeroed module block via VSC Write Module (0xD6).
        """
        # 512 bytes of zeros (cleared SMART module table)
        zero_buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD6, # VSC Write Module
                features=0x01, # Length in sectors
                sector_count=0x21, # Module ID 0x21 (SMART Table)
                lba=0x00,
                device=0x00,
                data_buffer=zero_buf,
                data_direction="out"
            )
        return res

    def wd_clear_glist_module(self) -> dict:
        """
        Clears WD G-List Module (0x32) by writing a zeroed defect table via VSC Write Module (0xD6).
        """
        zero_buf = bytearray(512)
        with self.controller as spt:
            res = spt.execute_sat_ata_command(
                command=0xD6,
                features=0x01,
                sector_count=0x32, # Module ID 0x32 (G-List)
                lba=0x00,
                device=0x00,
                data_buffer=zero_buf,
                data_direction="out"
            )
        return res

    # -------------------------------------------------------------
    # SAMSUNG VSC
    # -------------------------------------------------------------
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

    # -------------------------------------------------------------
    # ATA SANITIZE DEVICE & SECURITY ERASE
    # -------------------------------------------------------------
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
                command=0xB4, # ATA SANITIZE DEVICE
                features=feat,
                sector_count=0x00,
                lba=0x44617461, # Key pattern
                device=0x00,
                data_direction="none"
            )
        return res

    def ata_security_set_password(self, password: str = "Terminator123") -> dict:
        """Executes ATA SECURITY SET PASSWORD (0xF1)."""
        # Password sector: 2 bytes identifier (0 = User), 32 bytes password, padded with 0
        buf = bytearray(512)
        buf[0] = 0x00 # User password
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
        buf[0] = 0x01 if enhanced else 0x00 # 1 = Enhanced Erase
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
