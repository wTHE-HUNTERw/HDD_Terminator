"""
SPTI (SCSI Pass Through Interface) and SAT (SCSI / ATA Translation) Engine
Provides low-level ATA command dispatching over USB and direct SATA connections on Windows.
"""

import ctypes
from ctypes import wintypes
import struct
import sys

# Win32 Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = -1

# IOCTL codes
IOCTL_SCSI_PASS_THROUGH = 0x0004D004
IOCTL_SCSI_PASS_THROUGH_DIRECT = 0x0004D014
IOCTL_ATA_PASS_THROUGH = 0x0004D02C
IOCTL_ATA_PASS_THROUGH_DIRECT = 0x0004D030
IOCTL_STORAGE_QUERY_PROPERTY = 0x002D1400

# SCSI Pass Through Direct Constants
SCSI_IOCTL_DATA_OUT = 0
SCSI_IOCTL_DATA_IN = 1
SCSI_IOCTL_DATA_UNSPECIFIED = 2

class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("ScsiStatus", wintypes.BYTE),
        ("PathId", wintypes.BYTE),
        ("TargetId", wintypes.BYTE),
        ("Lun", wintypes.BYTE),
        ("CdbLength", wintypes.BYTE),
        ("SenseInfoLength", wintypes.BYTE),
        ("DataIn", wintypes.BYTE),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", wintypes.BYTE * 16),
    ]

class SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER(ctypes.Structure):
    _fields_ = [
        ("sptd", SCSI_PASS_THROUGH_DIRECT),
        ("Filler", wintypes.ULONG),
        ("SenseData", wintypes.BYTE * 64),
    ]

# Win32 API functions
kernel32 = ctypes.windll.kernel32

CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE
]
CreateFileW.restype = wintypes.HANDLE

DeviceIoControl = kernel32.DeviceIoControl
DeviceIoControl.argtypes = [
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID
]
DeviceIoControl.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

GetLastError = kernel32.GetLastError
GetLastError.restype = wintypes.DWORD


class SPTIController:
    """Manages raw device handle and command execution via SPTI / SAT."""

    def __init__(self, drive_path: str):
        """
        :param drive_path: e.g. "\\\\.\\PhysicalDrive1" or "\\\\.\\E:"
        """
        self.drive_path = drive_path
        self.handle = None

    def open(self, read_only=False) -> bool:
        access = FILE_SHARE_READ if read_only else (GENERIC_READ | GENERIC_WRITE)
        share_mode = FILE_SHARE_READ | FILE_SHARE_WRITE

        self.handle = CreateFileW(
            self.drive_path,
            access,
            share_mode,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None
        )

        if self.handle == INVALID_HANDLE_VALUE or self.handle is None or self.handle == 0:
            err = GetLastError()
            self.handle = None
            raise PermissionError(f"No se pudo abrir el dispositivo {self.drive_path}. Código Win32: {err}. Requiere ejecutarse como Administrador.")
        return True

    def close(self):
        if self.handle and self.handle != INVALID_HANDLE_VALUE:
            CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def execute_sat_ata_command(
        self,
        command: int,
        features: int = 0,
        sector_count: int = 0,
        lba: int = 0,
        device: int = 0,
        data_buffer: bytearray = None,
        data_direction: str = "in",  # "in", "out", "none"
        timeout_sec: int = 10,
        is_lba48: bool = False
    ) -> dict:
        """
        Executes an ATA command mapped into SCSI ATA PASS-THROUGH (16) (SAT-2 / SAT-3 standard).
        Opcode 0x85 (ATA PASS-THROUGH 16).
        """
        if not self.handle:
            self.open()

        sptwb = SCSI_PASS_THROUGH_DIRECT_WITH_BUFFER()
        ctypes.memset(ctypes.byref(sptwb), 0, ctypes.sizeof(sptwb))

        spt = sptwb.sptd
        spt.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        spt.CdbLength = 16
        spt.SenseInfoLength = 64
        spt.SenseInfoOffset = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT) + 4
        spt.TimeOutValue = timeout_sec

        buf_len = len(data_buffer) if data_buffer is not None else 0

        # Create ctypes buffer if needed
        c_buffer = None
        if buf_len > 0:
            c_buffer = (ctypes.c_ubyte * buf_len).from_buffer(data_buffer)
            spt.DataBuffer = ctypes.cast(ctypes.pointer(c_buffer), ctypes.c_void_p)
            spt.DataTransferLength = buf_len

        # Protocol mapping for SAT ATA PASS-THROUGH (16)
        # Protocol field (bits 4:1 of byte 1):
        # 3 = Non-data, 4 = PIO Data-In, 5 = PIO Data-Out, 6 = DMA
        if data_direction == "in" and buf_len > 0:
            spt.DataIn = SCSI_IOCTL_DATA_IN
            protocol = 4  # PIO Data-In
            t_dir = 1     # Transfer from device to system
            byt_blk = 1   # Transfer length in sectors
        elif data_direction == "out" and buf_len > 0:
            spt.DataIn = SCSI_IOCTL_DATA_OUT
            protocol = 5  # PIO Data-Out
            t_dir = 0     # Transfer from system to device
            byt_blk = 1
        else:
            spt.DataIn = SCSI_IOCTL_DATA_UNSPECIFIED
            protocol = 3  # Non-data
            t_dir = 0
            byt_blk = 0

        cdb = (wintypes.BYTE * 16)()
        cdb[0] = 0x85  # ATA PASS-THROUGH (16)
        cdb[1] = (protocol << 1) | (1 if is_lba48 else 0)
        # Byte 2: Flags (CK_COND=1, T_DIR, BYT_BLK, T_LEN=2 (sector_count))
        # CK_COND = 1 returns ATA status in Sense Data
        ck_cond = 1
        t_len = 2 if buf_len > 0 else 0  # 2: length specified in Sector_Count field
        cdb[2] = (ck_cond << 5) | (t_dir << 3) | (byt_blk << 2) | (t_len & 0x03)

        if is_lba48:
            cdb[3] = (features >> 8) & 0xFF
            cdb[4] = features & 0xFF
            cdb[5] = (sector_count >> 8) & 0xFF
            cdb[6] = sector_count & 0xFF
            cdb[7] = (lba >> 24) & 0xFF
            cdb[8] = lba & 0xFF
            cdb[9] = (lba >> 32) & 0xFF
            cdb[10] = (lba >> 8) & 0xFF
            cdb[11] = (lba >> 40) & 0xFF
            cdb[12] = (lba >> 16) & 0xFF
            cdb[13] = device & 0xFF
            cdb[14] = command & 0xFF
            cdb[15] = 0x00  # Control
        else:
            cdb[3] = 0
            cdb[4] = features & 0xFF
            cdb[5] = 0
            cdb[6] = sector_count & 0xFF
            cdb[7] = 0
            cdb[8] = lba & 0xFF
            cdb[9] = 0
            cdb[10] = (lba >> 8) & 0xFF
            cdb[11] = 0
            cdb[12] = (lba >> 16) & 0xFF
            cdb[13] = (device & 0xEF) | 0xA0 | ((lba >> 24) & 0x0F)
            cdb[14] = command & 0xFF
            cdb[15] = 0x00

        for i in range(16):
            spt.Cdb[i] = cdb[i]

        bytes_returned = wintypes.DWORD(0)
        success = DeviceIoControl(
            self.handle,
            IOCTL_SCSI_PASS_THROUGH_DIRECT,
            ctypes.byref(sptwb),
            ctypes.sizeof(sptwb),
            ctypes.byref(sptwb),
            ctypes.sizeof(sptwb),
            ctypes.byref(bytes_returned),
            None
        )

        last_error = GetLastError() if not success else 0
        scsi_status = sptwb.sptd.ScsiStatus

        sense_data = bytes(sptwb.SenseData)
        sense_key, asc, ascq = self._parse_scsi_sense(sense_data)
        ata_return_registers = self._parse_sat_sense_data(sense_data)

        ioctl_ok = bool(success) and last_error == 0
        command_ok, error_hint = self._evaluate_command_result(
            ioctl_ok=ioctl_ok,
            scsi_status=scsi_status,
            sense_key=sense_key,
            asc=asc,
            ata_registers=ata_return_registers
        )

        return {
            "success": command_ok,
            "ioctl_ok": ioctl_ok,
            "win32_error": last_error,
            "scsi_status": scsi_status,
            "sense_key": sense_key,
            "asc": asc,
            "ascq": ascq,
            "sense_data": sense_data,
            "ata_registers": ata_return_registers,
            "command_ok": command_ok,
            "error_hint": error_hint,
            "data": bytes(data_buffer) if data_buffer is not None else None
        }

    @staticmethod
    def _parse_scsi_sense(sense: bytes) -> tuple:
        """
        Extracts (sense_key, asc, ascq) from SCSI sense data.
        Supports descriptor format (0x72/0x73) and fixed format (0x70/0x71).
        """
        if len(sense) < 3:
            return (0xFF, 0xFF, 0xFF)
        response_code = sense[0] & 0x7F
        if response_code in (0x72, 0x73, 0x70, 0x71):
            if len(sense) < 14:
                return (sense[2] & 0x0F, 0xFF, 0xFF)
            return (sense[2] & 0x0F, sense[12], sense[13])
        return (sense[2] & 0x0F, 0xFF, 0xFF)

    @staticmethod
    def _evaluate_command_result(
        ioctl_ok: bool,
        scsi_status: int,
        sense_key: int,
        asc: int,
        ata_registers: dict
    ) -> tuple:
        """
        Determines whether the ATA command REALLY completed successfully and
        returns a human-readable hint when it did not.

        With CK_COND set, SAT always termininates with CHECK CONDITION even on
        success (RECOVERED ERROR / ATA PASS-THROUGH INFORMATION AVAILABLE), so
        the SCSI status alone is NOT a valid success indicator. The truth is in
        the ATA Status Return Descriptor: bit 0 (ERR) of the ATA status register
        and the ATA error register.
        """
        error_hint = None
        err_reg = ata_registers.get("error", 0)
        stat_reg = ata_registers.get("status", 0)

        if not ioctl_ok:
            return (False, "El IOCTL falló a nivel de sistema. Verifica permisos de Administrador y que el disco no esté en uso.")
        if ata_registers.get("has_descriptor"):
            if (stat_reg & 0x01) == 0 and err_reg == 0:
                return (True, None)
            if err_reg & 0x04:
                return (False, "El disco ABORTÓ el comando (Error ATA = ABRT): este comando no está soportado por el firmware del disco o requiere modo diagnóstico (ej. terminal TTL/F3).")
            return (False, f"Error ATA reportado por el disco: Status=0x{stat_reg:02X} Error=0x{err_reg:02X}.")
        if scsi_status == 0x00:
            return (True, None)
        if scsi_status == 0x02 and sense_key in (0x00, 0x01):
            return (True, None)  # CK_COND: CHECK CONDITION esperado en éxito (NO SENSE / RECOVERED ERROR)
        if sense_key == 0x05 and asc == 0x20:
            return (False, "El puente USB rechazó el opcode (INVALID COMMAND OPERATION CODE): los comandos de fabricante (VSC) suelen estar bloqueados por el bridge USB. Prueba con conexión SATA directa.")
        if sense_key == 0x0B:
            return (False, "Comando ABORTADO por el dispositivo o el bridge USB (ABORTED COMMAND).")
        if sense_key == 0x06:
            return (False, "El medio/dispositivo indica UNIT ATTENTION: estado no listo o medio cambiado.")
        return (False, f"SCSI Check Condition sin descriptor ATA: Sense Key=0x{sense_key:02X} ASC=0x{asc:02X}.")

    def _parse_sat_sense_data(self, sense: bytes) -> dict:
        """Parses ATA Status Return Descriptor from SCSI Sense Data (Descriptor Format, Response code 0x72/0x73)."""
        res = {
            "error": 0,
            "sector_count": 0,
            "lba": 0,
            "device": 0,
            "status": 0,
            "has_descriptor": False,
        }
        if len(sense) < 8:
            return res

        response_code = sense[0] & 0x7F
        if response_code in (0x72, 0x73):
            pos = 8
            while pos + 1 < len(sense):
                desc_type = sense[pos]
                desc_len = sense[pos + 1]
                if desc_type == 0x09 and desc_len >= 12:  # ATA Status Return Descriptor
                    desc_data = sense[pos + 2: pos + 2 + desc_len]
                    if len(desc_data) >= 12:
                        res["has_descriptor"] = True
                        res["error"] = desc_data[1]
                        res["sector_count"] = (desc_data[2] << 8) | desc_data[3]
                        lba_low = desc_data[5]
                        lba_mid = desc_data[7]
                        lba_high = desc_data[9]
                        res["lba"] = (lba_high << 16) | (lba_mid << 8) | lba_low
                        res["device"] = desc_data[10]
                        res["status"] = desc_data[11]
                    break
                pos += 2 + desc_len
        return res
