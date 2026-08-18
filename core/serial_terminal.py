"""
Serial / UART Firmware Diagnostic Terminal Manager
Handles high-speed serial communication with HDD PCB firmware ports (Seagate F3, WD, Toshiba, Hitachi).
"""

import threading
import time
import serial

class SerialTerminalManager:
    def __init__(self, data_received_callback=None, status_callback=None):
        self.serial_port = None
        self.is_connected = False
        self.read_thread = None
        self.stop_event = threading.Event()
        self.data_received_callback = data_received_callback
        self.status_callback = status_callback
        self.log_history = []

    def connect(self, port: str, baudrate: int = 38400, bytesize=8, parity='N', stopbits=1, timeout=0.1) -> bool:
        if self.is_connected:
            self.disconnect()

        try:
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout
            )
            self.is_connected = True
            self.stop_event.clear()
            self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
            self.read_thread.start()
            if self.status_callback:
                self.status_callback(True, f"Conectado a {port} a {baudrate} baudios.")
            return True
        except Exception as e:
            self.is_connected = False
            if self.status_callback:
                self.status_callback(False, f"Error al conectar con {port}: {str(e)}")
            return False

    def disconnect(self):
        self.stop_event.set()
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception:
                pass
        self.is_connected = False
        if self.status_callback:
            self.status_callback(False, "Desconectado.")

    def _reader_loop(self):
        while not self.stop_event.is_set() and self.serial_port and self.serial_port.is_open:
            try:
                waiting = self.serial_port.in_waiting
                if waiting > 0:
                    raw_bytes = self.serial_port.read(waiting)
                    text = raw_bytes.decode('ascii', errors='replace')
                    self.log_history.append(text)
                    if self.data_received_callback:
                        self.data_received_callback(raw_bytes, text)
                else:
                    time.sleep(0.02)
            except Exception as e:
                if not self.stop_event.is_set():
                    if self.status_callback:
                        self.status_callback(False, f"Error en lectura de puerto serial: {e}")
                break

    def send_text(self, text: str, append_newline: bool = True) -> bool:
        if not self.is_connected or not self.serial_port or not self.serial_port.is_open:
            return False
        try:
            payload = text
            if append_newline and not text.endswith("\r") and not text.endswith("\n"):
                payload += "\r\n"
            self.serial_port.write(payload.encode('ascii', errors='replace'))
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(False, f"Error al enviar datos: {e}")
            return False

    def send_raw_bytes(self, data: bytes) -> bool:
        if not self.is_connected or not self.serial_port or not self.serial_port.is_open:
            return False
        try:
            self.serial_port.write(data)
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(False, f"Error al enviar bytes: {e}")
            return False

    def send_ctrl_z(self):
        """Sends Ctrl+Z (0x1A), used to wake up Seagate F3 Terminal prompt."""
        return self.send_raw_bytes(b"\x1a")

    def send_ctrl_c(self):
        """Sends Ctrl+C (0x03), used to interrupt operations in firmware."""
        return self.send_raw_bytes(b"\x03")

    def send_break(self, duration: float = 0.25):
        """Sends serial BREAK signal."""
        if not self.is_connected or not self.serial_port:
            return False
        try:
            self.serial_port.send_break(duration)
            return True
        except Exception as e:
            if self.status_callback:
                self.status_callback(False, f"Error al enviar BREAK: {e}")
            return False

# Comprehensive Firmware Diagnostic & SMART Reset Macros
FIRMWARE_MACROS = {
    "Seagate F3": [
        {"name": "Ctrl+Z (Despertar F3 T>)", "action": "raw", "data": b"\x1a", "desc": "Envía 0x1A para despertar el prompt de terminal F3"},
        {"name": "1. Reset SMART Completo (N1,,22)", "action": "text", "data": "/1\rN1,,22\r", "desc": "Entra a Nivel 1 y borra contadores y atributos SMART"},
        {"name": "2. Limpiar G-List (i4,1,22)", "action": "text", "data": "/T\ri4,1,22\r", "desc": "Borra la lista G de sectores reasignados (Grown Defect List)"},
        {"name": "3. Reconstruir Translator (m0,6,2,,,,,22)", "action": "text", "data": "/T\rm0,6,2,,,,,22\r", "desc": "Regenera el traductor LBA ignorando la G-List (Fix Capacidad 0 / Busy)"},
        {"name": "4. Formatear + Rebuild G-List (m0,2,2,,,,,22)", "action": "text", "data": "/T\rm0,2,2,,,,,22\r", "desc": "Formatea partición de usuario y reconstruye tabla basada en defectos"},
        {"name": "5. Reset SMART Básico (1> N1)", "action": "text", "data": "/1\rN1\r", "desc": "Reseteo estándar de SMART en Nivel 1"},
        {"name": "Ver Non-Resident G-List (V40)", "action": "text", "data": "/T\rV40\r", "desc": "Muestra todas las entradas de sectores reasignados"},
        {"name": "Ver Primary P-List (V10)", "action": "text", "data": "/T\rV10\r", "desc": "Muestra la lista de defectos de fábrica (Primary Defect List)"},
        {"name": "Ver Tracking List (V2)", "action": "text", "data": "/T\rV2\r", "desc": "Muestra la lista de defectos T-List"},
        {"name": "Ver Slip List (V1)", "action": "text", "data": "/T\rV1\r", "desc": "Muestra la tabla de deslizamiento (Slip List)"},
        {"name": "Ver Atributos SMART (1> N5)", "action": "text", "data": "/1\rN5\r", "desc": "Vuelca la tabla SMART en consola"},
        {"name": "Info de Firmware (F)", "action": "text", "data": "/T\rF\r", "desc": "Muestra versión de firmware y cabezales"},
        {"name": "Desbloqueo Firmware F3 Lock", "action": "raw", "data": b"\x1a\x1a\x1a", "desc": "Secuencia de escape para terminales con handshake bloqueado"},
        {"name": "Motor: Spin Down (2> Z)", "action": "text", "data": "/2\rZ\r", "desc": "Detiene el motor del disco en Nivel 2"},
        {"name": "Motor: Spin Up (2> U)", "action": "text", "data": "/2\rU\r", "desc": "Enciende el motor del disco en Nivel 2"},
    ],
    "Western Digital": [
        {"name": "SuperOn Key (Desbloqueo)", "action": "text", "data": "\xcd\x00\x00\x00", "desc": "Envía comando SuperOn para habilitar comandos de servicio VSC"},
        {"name": "Clear G-List (CLRG)", "action": "text", "data": "CLRG\r", "desc": "Borra tabla de sectores reasignados en módulo 0x32"},
        {"name": "Clear Defect List (CLRDEF)", "action": "text", "data": "CLRDEF\r", "desc": "Limpia listas de defectos en el firmware"},
        {"name": "Directorios Firmware SA (DIR)", "action": "text", "data": "DIR\r", "desc": "Muestra tabla de módulos en el área de sistema"},
        {"name": "Estado de ROM (ROMS)", "action": "text", "data": "ROMS\r", "desc": "Inspecciona la memoria ROM del PCB"},
        {"name": "Prueba de Diagnóstico PCB (TEST)", "action": "text", "data": "TEST\r", "desc": "Ejecuta diagnóstico de memoria y bus del PCB"},
    ],
    "Toshiba": [
        {"name": "Despertar Terminal", "action": "raw", "data": b"\r\n\r\n", "desc": "Envía secuencias de retorno de carro para despertar consola"},
        {"name": "Ver Información (INFO)", "action": "text", "data": "INFO\r", "desc": "Muestra estado de firmware y geometría"},
        {"name": "Low Level Format / Defect Clear (M0)", "action": "text", "data": "/\rM0\r", "desc": "Formateo y reconstrucción de listas de defectos"},
        {"name": "Ver SMART (SMART)", "action": "text", "data": "SMART\r", "desc": "Muestra contadores de salud del disco"},
    ]
}
