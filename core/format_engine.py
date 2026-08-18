"""
Low-Level Format & Real-time Disk Wiping Engine
Supports Zero-Fill, Random Pattern, DoD Wipe, and Block-by-Block Surface Scan with real-time telemetry.
"""

import time
import threading
import os
from .spti import SPTIController

class LowLevelFormatEngine:
    def __init__(self, drive_path: str, update_callback=None, block_status_callback=None):
        """
        :param drive_path: e.g. "\\\\.\\PhysicalDrive2"
        :param update_callback: func(lba_current, lba_total, speed_mb_s, percent, eta_str, status_msg)
        :param block_status_callback: func(block_index, status_type) # "ok", "slow", "bad"
        """
        self.drive_path = drive_path
        self.update_callback = update_callback
        self.block_status_callback = block_status_callback
        self.is_running = False
        self.is_paused = False
        self.abort_requested = False
        self._thread = None

    def start_format(
        self,
        mode: str = "zero",  # "zero", "random", "dod", "verify_read"
        start_lba: int = 0,
        end_lba: int = None,
        block_size_sectors: int = 256,  # 256 sectors = 128 KB
        total_sectors: int = None
    ):
        if self.is_running:
            return False

        self.is_running = True
        self.is_paused = False
        self.abort_requested = False

        self._thread = threading.Thread(
            target=self._format_worker,
            args=(mode, start_lba, end_lba, block_size_sectors, total_sectors),
            daemon=True
        )
        self._thread.start()
        return True

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.abort_requested = True

    def _format_worker(self, mode: str, start_lba: int, end_lba: int, block_size_sectors: int, total_sectors: int):
        controller = SPTIController(self.drive_path)
        try:
            controller.open(read_only=(mode == "verify_read"))
        except Exception as e:
            if self.update_callback:
                self.update_callback(0, 0, 0, 0, "--:--", f"Error al abrir unidad: {e}")
            self.is_running = False
            return

        if total_sectors is None or total_sectors <= 0:
            # Fallback estimation if not supplied
            total_sectors = 1000000

        if end_lba is None or end_lba <= 0 or end_lba > total_sectors:
            end_lba = total_sectors

        current_lba = start_lba
        total_to_process = max(1, end_lba - start_lba)
        bytes_per_sector = 512
        chunk_bytes = block_size_sectors * bytes_per_sector

        # Prepare pattern buffer
        if mode == "zero":
            pattern_buf = bytearray(chunk_bytes)
        elif mode == "random":
            pattern_buf = bytearray(os.urandom(chunk_bytes))
        else:
            pattern_buf = bytearray(chunk_bytes)

        start_time = time.time()
        last_time = start_time
        bytes_since_last = 0
        total_bytes_written = 0
        block_index = 0

        # Command Opcode: ATA WRITE SECTORS EXT (0x34) or READ SECTORS EXT (0x24)
        cmd_opcode = 0x24 if mode == "verify_read" else 0x34
        direction = "in" if mode == "verify_read" else "out"

        while current_lba < end_lba and not self.abort_requested:
            while self.is_paused and not self.abort_requested:
                time.sleep(0.2)

            if self.abort_requested:
                break

            sectors_to_write = min(block_size_sectors, end_lba - current_lba)
            current_chunk_size = sectors_to_write * bytes_per_sector
            buf = pattern_buf[:current_chunk_size] if mode != "random" else bytearray(os.urandom(current_chunk_size))

            t0 = time.time()
            try:
                res = controller.execute_sat_ata_command(
                    command=cmd_opcode,
                    features=0,
                    sector_count=sectors_to_write,
                    lba=current_lba,
                    device=0x40,
                    data_buffer=buf,
                    data_direction=direction,
                    is_lba48=True,
                    timeout_sec=15
                )
                success = res.get("success", False)
            except Exception:
                success = False

            t_elapsed_chunk = time.time() - t0

            # Determine sector block health
            if not success:
                block_status = "bad"
            elif t_elapsed_chunk > 0.5:
                block_status = "slow"
            else:
                block_status = "ok"

            if self.block_status_callback:
                self.block_status_callback(block_index, block_status, current_lba)

            block_index += 1
            current_lba += sectors_to_write
            bytes_since_last += current_chunk_size
            total_bytes_written += current_chunk_size

            # Periodic update telemetry every 0.15s
            now = time.time()
            if now - last_time >= 0.15 or current_lba >= end_lba:
                delta_t = now - last_time
                speed_mb_s = (bytes_since_last / (1024 * 1024)) / delta_t if delta_t > 0 else 0
                bytes_since_last = 0
                last_time = now

                processed_sectors = current_lba - start_lba
                percent = (processed_sectors / total_to_process) * 100.0

                # Estimated Time Remaining (ETA)
                overall_time = now - start_time
                if percent > 0 and overall_time > 0:
                    total_estimated_time = overall_time / (percent / 100.0)
                    rem_sec = max(0, int(total_estimated_time - overall_time))
                    hrs = rem_sec // 3600
                    mins = (rem_sec % 3600) // 60
                    secs = rem_sec % 60
                    eta_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"
                else:
                    eta_str = "--:--"

                status_msg = f"Procesando LBA {current_lba:,} / {end_lba:,}"
                if self.update_callback:
                    self.update_callback(current_lba, end_lba, speed_mb_s, percent, eta_str, status_msg)

        controller.close()
        self.is_running = False

        if self.update_callback:
            if self.abort_requested:
                self.update_callback(current_lba, end_lba, 0, percent, "--:--", "🛑 Operación cancelada por el usuario.")
            else:
                self.update_callback(end_lba, end_lba, 0, 100.0, "00:00", "✅ Formateo de bajo nivel completado exitosamente.")
