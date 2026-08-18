@echo off
title Compilando y Firmando HDD Terminator Ultimate (.EXE)...
cd /d "%~dp0"
echo =======================================================
echo   COMPILANDO HDD TERMINATOR ULTIMATE A EJECUTABLE (.EXE)
echo =======================================================
echo.

pyinstaller --noconfirm HDD_Terminator_Ultimate.spec

echo.
if exist "dist\HDD_Terminator_Ultimate.exe" (
    echo =======================================================
    echo   FIRMANDO DIGITALMENTE EL EJECUTABLE (AUTHENTICODE)...
    echo =======================================================
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like '*HDD Terminator*' } | Select-Object -First 1; ^
        if (-not $cert) { ^
            $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=wTHE-HUNTERw Developer, O=HDD Terminator Ultimate' -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddYears(5); ^
            Export-Certificate -Cert $cert -FilePath 'HDD_Terminator_Certificate.cer' | Out-Null; ^
        } ^
        $sig = Set-AuthenticodeSignature -FilePath 'dist\HDD_Terminator_Ultimate.exe' -Certificate $cert -TimestampServer 'http://timestamp.digicert.com' -HashAlgorithm SHA256; ^
        Write-Host 'Firma completada:' $sig.Status"
    
    echo.
    echo =======================================================
    echo   EXITO: Ejecutable generado y firmado en:
    echo   dist\HDD_Terminator_Ultimate.exe
    echo =======================================================
) else (
    echo [ERROR] No se pudo generar el ejecutable.
)
pause
