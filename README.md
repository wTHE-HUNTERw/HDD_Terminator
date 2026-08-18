# ⚡ HDD Terminator Ultimate - Suite Definitiva de Diagnóstico, Formateo LLF & Modding SPI

**HDD Terminator Ultimate** es la solución integral y profesional para el tratamiento, recuperación, formateo a bajo nivel y modificación de firmware de discos duros mecánicos (HDD) y de estado sólido (SSD).

---

## 🚀 Módulos y Funcionalidades Principales

### 1. 💽 Comandos ATA & SMART (Case USB / SATA Pass-Through)
- **ATA IDENTIFY (`0xEC`)**: Extracción de modelo, número de serie, versión de firmware, soporte LBA48 y capacidades de seguridad.
- **Salud & Diagnóstico SMART (`0xB0 / 0xD0 / 0xDA`)**: Monitorización de los 30 atributos SMART con semáforo de riesgo para sectores reasignados (ID 5) y pendientes (ID 197).
- **Subcomandos ATA SMART**: Habilitar (`0xD8`), Deshabilitar (`0xD9`), Self-Test Corto y Extendido (`0xD4`).
- **Lector de Sectores LBA**: Lectura directa de cualquier sector LBA (512B) a visor hexadecimal.
- **Consola ATA Raw**: Despachador universal de registros ATA (`Command`, `Features`, `LBA`, `Device`, `Buffer`).

### 2. 🧹 Formateo a Bajo Nivel en Tiempo Real (Visual Map)
- **Modos de Formateo**:
  - `Zero-Fill`: Llenado rápido de ceros (`0x00`) por sectores de alta velocidad.
  - `Random Pattern`: Sobreescritura de grado de seguridad con patrones aleatorios criptográficos.
  - `Surface Read Scan`: Escaneo de superficie no destructivo para verificar tiempos de respuesta.
- **Telemetría en Vivo**:
  - Velocímetro de escritura en tiempo real (`MB/s`).
  - Barra de progreso porcentual (`0.0% - 100.0%`).
  - Tiempo transcurrido y tiempo restante estimado (ETA).
- **Mapa de Superficie Visual en Tiempo Real (Estilo Victoria / MHDD)**:
  - Cuadrícula interactiva con código de colores según el tiempo de respuesta del sector:
    - 🟩 **Verde**: Excelente (<50 ms)
    - 🟨 **Amarillo**: Lento (50 - 500 ms)
    - 🟥 **Rojo**: Sector Dañado / Bad Sector (Error de lectura/escritura)
- **Controles de Ejecución**: Iniciar, Pausar, Reanudar y Cancelar en cualquier momento.

### 3. 🔌 Terminal Serial / TTL (Firmware PCB)
- Consola bidireccional en tiempo real para interacción con el microcódigo (Seagate F3, Western Digital, Toshiba).
- Botones de control: `Ctrl+Z` (Wakeup Prompt), `Ctrl+C` (Interrupción), `Break`.
- Catálogo de macros de 1-clic: `N1,,22` (Reset SMART), `i4,1,22` (Clear G-List), `m0,6,2,,,,,22` (Translator Regen), `CLRG` (WD Clear G-List), `M0` (Toshiba LLF).

### 4. 🧪 Laboratorio VSC & SMART Reset Avanzado (Ingeniería Inversa)
- **Western Digital VSC**: Desbloqueo SuperOn (`0x80`), sobreescritura con ceros del **Módulo 0x21 (SMART)** y **Módulo 0x32 (G-List)** vía ATA Pass-Through sobre el cable SATA/USB.
- **Samsung VSC**: Acceso a Service Area (`0xDF`) y borrado de logs (`0xE0`).
- **ATA Sanitize & Enhanced Security Erase**: Borrado por hardware a nivel de microcódigo.

### 5. 💾 Editor de Memoria SPI Flash & Parcheador ROM (Winbond 25Q80 / CH341A)
- **Editor Hexadecimal Interactivo**: Visualización y edición byte a byte de volcados de memoria ROM (`.bin`, `.rom`, `.dat`).
- **Buscador Hex & ASCII**: Búsqueda rápida de cadenas, números de serie y firmas de cabezales.
- **Parcheador de Firmware Automático**:
  - **Desbloqueo de Terminal Serie Seagate Rosewood / Grenada (Bypass Handshake Lock)**.
  - **Editor de Número de Serie de Fábrica**.
- **Guardado y Exportación**: Genera el archivo `.bin` listo para flashear directamente con el programador **CH341A / CH340** (NeoProgrammer / AsProgrammer).
- **Diagrama de Conexión**: Pinout completo de Winbond 25Q80 a CH341A (3.3V).

---

## 📋 Requisitos e Instalación

### Requisitos:
1. **Python 3.10 o superior**
2. Librerías requeridas (ya instaladas en el sistema):
   ```bash
   pip install customtkinter pyserial
   ```

### ⚠️ Permisos de Administrador en Windows
Para que Windows permita enviar comandos directos a `\\.\PhysicalDriveX` (discos físicos USB), la aplicación **debe ejecutarse con privilegios de Administrador**.

---

## 🖥️ Cómo Ejecutar la Aplicación

### Opción 1: Con el lanzador rápido (Recomendado)
Haz doble clic en el archivo **`run.bat`**. Este script solicitará permisos de Administrador automáticamente y abrirá la interfaz.

### Opción 2: Desde la terminal de comandos (CMD / PowerShell como Administrador)
```powershell
python main.py
```

---

## 🛠️ Conexión de Hardware

### Caso A: Disco en Case USB
1. Conecta el disco duro al Case USB o adaptador SATA-USB y conéctalo al puerto USB de tu computadora.
2. Abre la aplicación y ve a la pestaña **Comandos ATA / Case USB**.
3. Selecciona la unidad física correspondiente (identificada con `[USB]`).
4. Haz clic en **ATA IDENTIFY** o **Leer Atributos SMART**.

### Caso B: Conexión al Terminal Serial/TTL del PCB (ej. Seagate F3)
1. Conecta un adaptador USB-Serial TTL (configurado a **3.3V**):
   - **TX del adaptador** -> **RX del puerto de diagnóstico del disco**
   - **RX del adaptador** -> **TX del puerto de diagnóstico del disco**
   - **GND del adaptador** -> **GND del disco**
   *(Nota: NO conectes el pin VCC/5V del adaptador al disco; el disco debe alimentarse por su propia fuente de alimentación).*
2. En la aplicación, ve a la pestaña **Terminal Serial / TTL**.
3. Selecciona el puerto COM de tu adaptador TTL y la velocidad adecuada (ej. **38400** baudios para Seagate).
4. Haz clic en **⚡ Conectar** y luego presiona **Ctrl+Z** para despertar el prompt del disco (`F3 T>`).
