from __future__ import annotations

import contextlib
import enum
import secrets
import string
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional
from uuid import UUID, uuid4

import shell_interface as sh
from loguru import logger


class InvalidDecryptedDevice(ValueError):
    pass


class ValidCompressions(enum.Enum):
    LZO = "lzo"
    ZLIB = "zlib"
    ZLIB1 = "zlib:1"
    ZLIB2 = "zlib:2"
    ZLIB3 = "zlib:3"
    ZLIB4 = "zlib:4"
    ZLIB5 = "zlib:5"
    ZLIB6 = "zlib:6"
    ZLIB7 = "zlib:7"
    ZLIB8 = "zlib:8"
    ZLIB9 = "zlib:9"
    ZSTD = "zstd"
    ZSTD1 = "zstd:1"
    ZSTD2 = "zstd:2"
    ZSTD3 = "zstd:3"
    ZSTD4 = "zstd:4"
    ZSTD5 = "zstd:5"
    ZSTD6 = "zstd:6"
    ZSTD7 = "zstd:7"
    ZSTD8 = "zstd:8"
    ZSTD9 = "zstd:9"
    ZSTD10 = "zstd:10"
    ZSTD11 = "zstd:11"
    ZSTD12 = "zstd:12"
    ZSTD13 = "zstd:13"
    ZSTD14 = "zstd:14"
    ZSTD15 = "zstd:15"


@contextlib.contextmanager
def decrypted_device(device: Path, pass_cmd: str):
    decrypted = open_encrypted_device(device, pass_cmd)
    logger.success(f"Speichermedium {device} erfolgreich entschlüsselt.")
    try:
        yield decrypted
    finally:
        close_decrypted_device(decrypted)
        logger.success(
            f"Verschlüsselung des Speichermediums {device} erfolgreich geschlossen."
        )


@contextlib.contextmanager
def mounted_device(device: Path, compression: Optional[ValidCompressions]):
    if is_mounted(device):
        unmount_device(device)
    with TemporaryDirectory() as td:
        mount_dir = Path(td)
        mount_btrfs_device(device, Path(mount_dir), compression)
        logger.success(
            f"Speichermedium {device} erfolgreich nach {mount_dir} gemountet."
        )
        try:
            yield Path(mount_dir)
        finally:
            unmount_device(device)
            logger.success(f"Speichermedium {device} erfolgreich ausgehangen.")


@contextlib.contextmanager
def symbolic_link(src: Path, dest: Path):
    """Create an symbolic link from `src` to `dest`

    This context manager will create a symbolic link from src to dest. It
    differentiates itself from `Path.link_to()` by …:

        * … creating the link with root privileges. This allows to limit root
          permissions to only the necessary parts of the program.

        * … ensuring that the link gets removed after usage.

    Parameters:
    -----------
    src: Path to source; can be anything that has a filesystem path
    dest: Path to destination file

    Returns:
    --------
    The value of `dest.absolute()` will be returned.
    """

    if not src.exists():
        raise FileNotFoundError
    if dest.exists():
        raise FileExistsError
    absolute_dest = dest.absolute()
    ln_cmd: sh.StrPathList = ["sudo", "ln", "-s", src.absolute(), absolute_dest]
    sh.run_cmd(cmd=ln_cmd)
    logger.success(f"Symlink von {src} nach {dest} erfolgreich erstellt.")
    try:
        yield absolute_dest
    finally:
        # In case the link destination vanished, the program must not crash. After
        # all, the aimed for state has been reached.
        rm_cmd: sh.StrPathList = ["sudo", "rm", "-f", absolute_dest]
        sh.run_cmd(cmd=rm_cmd)
        logger.success(f"Symlink von {src} nach {dest} erfolgreich entfernt.")


def mount_btrfs_device(
    device: Path, mount_dir: Path, compression: Optional[ValidCompressions]
) -> None:
    cmd: sh.StrPathList = [
        "sudo",
        "mount",
        device,
        mount_dir,
    ]
    if compression is not None:
        cmd.extend(["-o", f"compress={compression.value}"])
    sh.run_cmd(cmd=cmd)


def is_mounted(dest: Path) -> bool:
    dest_as_str = str(dest)
    try:
        mount_dest = get_mounted_devices()[dest_as_str]
        logger.info(f"Mount des Speichermediums {dest} in {mount_dest} gefunden.")
    except KeyError:
        logger.info(f"Kein Mountpunkt für Speichermedium {dest} gefunden.")
        return False
    return True


def get_mounted_devices() -> dict[str, set[Path]]:
    raw_mounts = sh.run_cmd(cmd=["mount"], capture_output=True)
    mount_lines = raw_mounts.stdout.decode().splitlines()
    mount_points = defaultdict(set)
    for line in mount_lines:
        device = line.split()[0]
        dest = Path(line.split()[2])
        mount_points[device].add(dest)
    return dict(mount_points)


def unmount_device(device: Path) -> None:
    cmd: sh.StrPathList = ["sudo", "umount", device]
    sh.run_cmd(cmd=cmd)


def open_encrypted_device(device: Path, pass_cmd: str) -> Path:
    map_name = device.name
    decrypt_cmd: sh.StrPathList = ["sudo", "cryptsetup", "open", device, map_name]
    sh.pipe_pass_cmd_to_real_cmd(pass_cmd, decrypt_cmd)
    return Path("/dev/mapper/") / map_name


def close_decrypted_device(device: Path) -> None:
    if device.parent != Path("/dev/mapper"):
        raise InvalidDecryptedDevice
    map_name = device.name
    close_cmd = ["sudo", "cryptsetup", "close", map_name]
    sh.run_cmd(cmd=close_cmd)


def encrypt_device(device: Path, password_cmd: str) -> UUID:
    new_uuid = uuid4()
    format_cmd: sh.StrPathList = [
        "sudo",
        "cryptsetup",
        "luksFormat",
        "--uuid",
        str(new_uuid),
        device,
    ]
    sh.pipe_pass_cmd_to_real_cmd(pass_cmd=password_cmd, command=format_cmd)
    return new_uuid


def mkfs_btrfs(file: Path) -> None:
    cmd: sh.StrPathList = ["sudo", "mkfs.btrfs", file]
    sh.run_cmd(cmd=cmd)


def generate_passcmd() -> str:
    """
    Generate `echo` safe password and return PassCmd

    Returns
    -------
    str
        password command producing the password
    """
    n_chars = 16
    alphabet = string.ascii_letters + string.digits
    passphrase = "".join(secrets.choice(alphabet) for _ in range(n_chars))
    return f"echo {passphrase}"
