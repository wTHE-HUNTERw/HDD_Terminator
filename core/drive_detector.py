"""
Drive and Port Detector
Scans Windows physical drives (USB, SATA, NVMe) and Serial/COM ports (FTDI, CH340, CP2102, etc.).
"""

import subprocess
import json
import os
import sys
import serial.tools.list_ports

def get_physical_drives():
    """
    Returns a list of physical drives detected by Windows with bus type, model, size, and drive letters.
    """
    drives = []
    
    # Run PowerShell query to get Win32_DiskDrive information in JSON format
    ps_cmd = (
        "Get-CimInstance Win32_DiskDrive | ForEach-Object { "
        "$d = $_; "
        "$parts = Get-CimAssociatedInstance -InputObject $d -ResultClassName Win32_DiskPartition; "
        "$vols = $parts | ForEach-Object { Get-CimAssociatedInstance -InputObject $_ -ResultClassName Win32_LogicalDisk }; "
        "[PSCustomObject]@{ "
        "DeviceId = $d.DeviceId; "
        "Index = $d.Index; "
        "Model = $d.Model; "
        "InterfaceType = $d.InterfaceType; "
        "MediaType = $d.MediaType; "
        "Size = $d.Size; "
        "SerialNumber = $d.SerialNumber; "
        "Partitions = $d.Partitions; "
        "DriveLetters = ($vols.DeviceID -join ', ') "
        "} "
        "} | ConvertTo-Json -Compress"
    )

    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            timeout=10
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            for item in data:
                size_bytes = int(item.get("Size") or 0)
                size_gb = size_bytes / (1024 ** 3)
                is_usb = "USB" in str(item.get("InterfaceType", "")).upper() or "USB" in str(item.get("Model", "")).upper()
                drives.append({
                    "path": item.get("DeviceId", f"\\\\.\\PhysicalDrive{item.get('Index')}"),
                    "index": item.get("Index"),
                    "model": item.get("Model", "Dispositivo Desconocido"),
                    "interface": item.get("InterfaceType", "Desconocido"),
                    "is_usb": is_usb,
                    "size_bytes": size_bytes,
                    "size_str": f"{size_gb:.2f} GB" if size_gb >= 1 else f"{size_bytes / (1024**2):.1f} MB",
                    "serial": (item.get("SerialNumber") or "").strip(),
                    "letters": item.get("DriveLetters", ""),
                })
    except Exception as e:
        # Fallback basic scan if PowerShell query fails
        for i in range(16):
            drives.append({
                "path": f"\\\\.\\PhysicalDrive{i}",
                "index": i,
                "model": f"PhysicalDrive {i}",
                "interface": "Auto-Detect",
                "is_usb": False,
                "size_bytes": 0,
                "size_str": "Desconocido",
                "serial": "",
                "letters": "",
            })

    return drives

def get_serial_ports():
    """
    Returns list of available serial COM ports with details (VID, PID, description).
    """
    ports = []
    for p in serial.tools.list_ports.comports():
        ports.append({
            "port": p.device,
            "description": p.description,
            "hwid": p.hwid,
            "vid": f"{p.vid:04X}" if p.vid else "N/A",
            "pid": f"{p.pid:04X}" if p.pid else "N/A",
            "manufacturer": p.manufacturer or "Desconocido",
        })
    return ports
