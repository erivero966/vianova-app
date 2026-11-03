"""Respaldo cifrado de la base de datos hacia almacenamiento en la nube (política de seguridad de la información).

Reglas que aplica el script:
  1. Nunca respalda en discos externos ni medios removibles (USB, discos portátiles, tarjetas SD): si el destino
     está en un medio removible o en un punto de montaje típico de discos externos, se niega a continuar.
  2. El respaldo se cifra (Fernet, AES-128-CBC + HMAC-SHA256) con una clave propia de respaldos
     (VIANOVA_BACKUP_KEY), distinta de la clave de cifrado de campos, que se guarda en el gestor de secretos.
  3. Cada ambiente se respalda por separado y el nombre del archivo incluye el ambiente; un respaldo de producción
     no puede restaurarse en desarrollo ni en pruebas.
  4. Retención: se conservan los últimos N respaldos (VIANOVA_BACKUP_RETENTION, 14 por defecto).

Destinos admitidos (VIANOVA_BACKUP_DEST):
  s3://bucket/prefijo      → almacenamiento de objetos compatible con S3 (requiere boto3 y credenciales IAM)
  rclone:remoto:carpeta    → cualquier nube soportada por rclone (Google Drive institucional, OneDrive, etc.)
  /ruta/local              → SOLO como área de preparación en el mismo servidor (no removible), p. ej. un volumen
                             del proveedor de nube; nunca un disco externo.

Uso:
  python backup.py crear
  python backup.py restaurar ARCHIVO.vbk        (solo en el mismo ambiente que lo generó)
"""
import argparse
import datetime as dt
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

from app import config

EXTERNAL_MOUNT_HINTS = ("/media/", "/run/media/", "/mnt/usb", "/mnt/external", "/volumes/")


class DestinoNoPermitido(Exception):
    pass


def _linux_removable(path: Path) -> bool:
    """Revisa en /sys/block si el dispositivo que contiene la ruta es removible o está conectado por USB."""
    try:
        st = os.stat(path)
        major, minor = os.major(st.st_dev), os.minor(st.st_dev)
        dev = Path(f"/sys/dev/block/{major}:{minor}").resolve()
        for p in [dev, *dev.parents]:
            rem = p / "removable"
            if rem.exists() and rem.read_text().strip() == "1":
                return True
            if "usb" in p.name:
                return True
    except (OSError, ValueError):
        pass
    return False


def _windows_removable(path: Path) -> bool:
    try:
        import ctypes
        drive = str(path.resolve().drive) + "\\"
        DRIVE_REMOVABLE, DRIVE_REMOTE_OK = 2, 4
        return ctypes.windll.kernel32.GetDriveTypeW(drive) == DRIVE_REMOVABLE
    except Exception:
        return False


def es_disco_externo(path: Path) -> bool:
    p = str(path.resolve()).replace("\\", "/").lower() + "/"
    if any(h in p for h in EXTERNAL_MOUNT_HINTS):
        return True
    if platform.system() == "Windows":
        return _windows_removable(path)
    if platform.system() == "Linux":
        probe = path if path.exists() else path.parent
        while not probe.exists():
            probe = probe.parent
        return _linux_removable(probe)
    return False


def validar_destino(dest: str) -> str:
    if not dest:
        raise DestinoNoPermitido("Defina VIANOVA_BACKUP_DEST (s3://..., rclone:... o un volumen del servidor).")
    if dest.startswith(("s3://", "rclone:")):
        return "nube"
    if es_disco_externo(Path(dest)):
        raise DestinoNoPermitido(f"'{dest}' está en un disco externo o removible. La política lo prohíbe: "
                                 "los respaldos van a almacenamiento en la nube institucional.")
    if config.IS_PRODUCTION:
        raise DestinoNoPermitido("En producción el destino debe ser almacenamiento en la nube (s3:// o rclone:).")
    return "local"


def _clave() -> Fernet:
    k = os.getenv("VIANOVA_BACKUP_KEY")
    if not k:
        if config.IS_PRODUCTION:
            raise SystemExit("Defina VIANOVA_BACKUP_KEY (clave de respaldos guardada en el gestor de secretos).")
        f = config.DATA_DIR / ".backup.key"
        if not f.exists():
            f.write_bytes(Fernet.generate_key())
        k = f.read_text().strip()
    return Fernet(k.encode() if isinstance(k, str) else k)


def _volcar(tmp: Path) -> Path:
    out = tmp / "vianova.dump"
    url = config.DATABASE_URL
    if url.startswith("sqlite"):
        src = sqlite3.connect(url.split("sqlite:///", 1)[1])
        dst = sqlite3.connect(out)
        src.backup(dst)                       # copia consistente aunque la app esté en uso
        src.close(); dst.close()
    else:
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", f"--file={out}",
                        url.replace("postgresql+psycopg://", "postgresql://")], check=True)
    return out


def crear() -> Path:
    dest = os.getenv("VIANOVA_BACKUP_DEST", "")
    tipo = validar_destino(dest)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"vianova-{config.APP_ENV}-{stamp}.vbk"
    with tempfile.TemporaryDirectory() as td:
        dump = _volcar(Path(td))
        enc = Path(td) / name
        enc.write_bytes(_clave().encrypt(f"{config.APP_ENV}\n".encode() + dump.read_bytes()))
        if dest.startswith("s3://"):
            import boto3
            bucket, _, prefix = dest[5:].partition("/")
            boto3.client("s3").upload_file(str(enc), bucket, f"{prefix.rstrip('/')}/{name}".lstrip("/"),
                                           ExtraArgs={"ServerSideEncryption": "AES256"})
        elif dest.startswith("rclone:"):
            subprocess.run(["rclone", "copy", str(enc), dest[len("rclone:"):]], check=True)
        else:
            d = Path(dest); d.mkdir(parents=True, exist_ok=True)
            shutil.copy2(enc, d / name)
            _retener(d)
    print(f"Respaldo cifrado creado: {name} → {dest} ({tipo})")
    return Path(name)


def _retener(d: Path) -> None:
    keep = int(os.getenv("VIANOVA_BACKUP_RETENTION", "14"))
    files = sorted(d.glob(f"vianova-{config.APP_ENV}-*.vbk"))
    for f in files[:-keep]:
        f.unlink()


def restaurar(archivo: str) -> None:
    raw = _clave().decrypt(Path(archivo).read_bytes())
    env, _, data = raw.partition(b"\n")
    if env.decode() != config.APP_ENV:
        raise SystemExit(f"El respaldo es del ambiente '{env.decode()}' y no puede restaurarse en '{config.APP_ENV}'. "
                         "Los datos de un ambiente nunca se copian a otro.")
    if not config.DATABASE_URL.startswith("sqlite"):
        raise SystemExit("Para PostgreSQL use pg_restore con el archivo descifrado, siguiendo el procedimiento operativo.")
    target = Path(config.DATABASE_URL.split("sqlite:///", 1)[1])
    target.write_bytes(data)
    print(f"Base restaurada en {target}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("crear")
    r = sub.add_parser("restaurar"); r.add_argument("archivo")
    a = ap.parse_args()
    try:
        crear() if a.cmd == "crear" else restaurar(a.archivo)
    except DestinoNoPermitido as e:
        print("RESPALDO RECHAZADO:", e, file=sys.stderr)
        sys.exit(2)
