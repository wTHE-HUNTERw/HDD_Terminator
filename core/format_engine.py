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
        mode: str = "zero",  # "zero", "random", "dod", "gutmann", "verify_read"
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

        if not block_size_sectors or block_size_sectors <= 0:
            block_size_sectors = 2048 if total_sectors >= 500_000_000 else 512

        bytes_per_sector = 512
        chunk_bytes = block_size_sectors * bytes_per_sector

        # Determine pass list based on mode
        if mode == "dod":
            # DoD 5220.22-M Standard: 3 passes
            # Pass 1: Write all zeros (0x00)
            # Pass 2: Write all ones (0xFF)
            # Pass 3: Write random pattern
            passes = [
                ("DoD Paso 1/3: Zero-Fill (0x00)", "zero"),
                ("DoD Paso 2/3: One-Fill (0xFF)", "ones"),
                ("DoD Paso 3/3: Random Pattern", "random"),
            ]
        elif mode == "gutmann":
            # Gutmann method: 35 passes with specific patterns
            gutmann_patterns = [
                ("random",), ("random",), ("random",), ("random",),  # 1-4: Random
                (0x55,), (0xAA,), (0x92, 0x49, 0x24), (0x49, 0x24, 0x92),  # 5-8
                (0x24, 0x92, 0x49), (0x00,), (0x11,), (0x22,),  # 9-12
                (0x33,), (0x44,), (0x55,), (0x66,),  # 13-16
                (0x77,), (0x88,), (0x99,), (0xAA,),  # 17-20
                (0xBB,), (0xCC,), (0xDD,), (0xEE,),  # 21-24
                (0xFF,), (0x92, 0x49, 0x24), (0x49, 0x24, 0x92), (0x24, 0x92, 0x49),  # 25-28
                (0x6D, 0xB6, 0xDB), (0xB6, 0xDB, 0x6D), (0xDB, 0x6D, 0xB6),  # 29-31
                ("random",), ("random",), ("random",), ("random",),  # 32-35: Random
            ]
            passes = []
            for idx, pat in enumerate(gutmann_patterns, 1):
                if pat == ("random",):
                    passes.append((f"Gutmann Paso {idx}/35: Random", "random"))
                else:
                    passes.append((f"Gutmann Paso {idx}/35: Pattern 0x{pat[0]:02X}", "pattern", pat))
        else:
            # Single-pass modes
            passes = [(f"Procesando ({mode.upper()})", mode)]

        total_passes = len(passes)

        for pass_idx, pass_info in enumerate(passes):
            if self.abort_requested:
                break

            pass_label = pass_info[0]
            pass_mode = pass_info[1]

            # Generate pattern buffer for this pass
            if pass_mode == "zero":
                pattern_buf = bytearray(chunk_bytes)  # all 0x00
            elif pass_mode == "ones":
                pattern_buf = bytearray(b'\xFF' * chunk_bytes)
            elif pass_mode == "random":
                pattern_buf = bytearray(os.urandom(chunk_bytes))
            elif pass_mode == "pattern" and len(pass_info) > 2:
                pat_bytes = bytes(pass_info[2])
                repeats = (chunk_bytes // len(pat_bytes)) + 1
                pattern_buf = bytearray((pat_bytes * repeats)[:chunk_bytes])
            elif pass_mode == "verify_read":
                pattern_buf = bytearray(chunk_bytes)
            else:
                pattern_buf = bytearray(chunk_bytes)

            # ATA opcode
            cmd_opcode = 0x24 if pass_mode == "verify_read" else 0x34
            direction = "in" if pass_mode == "verify_read" else "out"

            current_lba = start_lba
            total_to_process = max(1, end_lba - start_lba)
            start_time = time.time()
            last_time = start_time
            bytes_since_last = 0
            block_index = 0

            while current_lba < end_lba and not self.abort_requested:
                while self.is_paused and not self.abort_requested:
                    time.sleep(0.2)

                if self.abort_requested:
                    break

                sectors_to_write = min(block_size_sectors, end_lba - current_lba)
                current_chunk_size = sectors_to_write * bytes_per_sector
                if pass_mode == "random":
                    buf = bytearray(os.urandom(current_chunk_size))
                else:
                    buf = pattern_buf[:current_chunk_size]

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

                # Periodic update telemetry every 0.15s
                now = time.time()
                if now - last_time >= 0.15 or current_lba >= end_lba:
                    delta_t = now - last_time
                    speed_mb_s = (bytes_since_last / (1024 * 1024)) / delta_t if delta_t > 0 else 0
                    bytes_since_last = 0
                    last_time = now

                    processed_sectors = current_lba - start_lba
                    # Calculate overall percent including multi-pass progress
                    pass_percent = (processed_sectors / total_to_process) * 100.0
                    overall_percent = ((pass_idx * 100.0) + pass_percent) / total_passes

                    # Estimated Time Remaining (ETA) for current pass
                    overall_time = now - start_time
                    if pass_percent > 0 and overall_time > 0:
                        total_estimated_time = overall_time / (pass_percent / 100.0)
                        rem_sec = max(0, int(total_estimated_time - overall_time))
                        # Account for remaining passes
                        remaining_passes = total_passes - pass_idx - 1
                        rem_sec += int(remaining_passes * total_estimated_time)
                        hrs = rem_sec // 3600
                        mins = (rem_sec % 3600) // 60
                        secs = rem_sec % 60
                        eta_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"
                    else:
                        eta_str = "--:--"

                    status_msg = f"{pass_label} | LBA {current_lba:,} / {end_lba:,}"
                    if self.update_callback:
                        self.update_callback(current_lba, end_lba, speed_mb_s, overall_percent, eta_str, status_msg)

        controller.close()
        self.is_running = False

        if self.update_callback:
            if self.abort_requested:
                self.update_callback(current_lba, end_lba, 0, overall_percent if 'overall_percent' in dir() else 0, "--:--", "🛑 Operación cancelada por el usuario.")
            else:
                self.update_callback(end_lba, end_lba, 0, 100.0, "00:00", "✅ Formateo de bajo nivel completado exitosamente.")
