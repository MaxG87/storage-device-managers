from __future__ import annotations

import contextlib
import enum
import secrets
import string
from collections import defaultdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator, Optional, Union
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
def decrypted_device(device: Path, pass_cmd: str) -> Iterator[Path]:
    """Decrypt a given device using pass_cmd

    Given a device and a shell command that outputs a password on STDOUT, this
    context manager will open the device using `cryptsetup`. Upon exit, the
    device is closed again.

    Note that pass_cmd will directly be executed in a subshell. Therefore, DO NOT
    USE UNTRUSTED `pass_cmd`!

    Parameters:
    -----------
    device
        file-like object to be opened with `cryptsetup`
    pass_cmd
        command that prints the device's password on STDOUT

    Returns:
    --------
    Path
        destination of opened device
    """
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
def mounted_device(
    device: Path, compression: Optional[ValidCompressions] = None
) -> Iterator[Path]:
    """Mount a given BtrFS device

    Given a path pointing to a file-like object, this context manager will
    mount it to some temporary directory and return its path. Upon exit, the
    file-like object is unmounted again.

    The filesystem of `device` must be BtrFS. While technically other file
    systems might work too, this behaviour is not guaranteed and might be
    broken without further notice!

    If `compression` is provided, a mount option specifying the transparent
    file system compression is set.

    Parameters:
    -----------
    device
        file-like object to be mounted
    compression
        compression level to be used by BtrFS

    Returns:
    --------
    Path
        directory to which `device` was mounted
    """
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
def symbolic_link(src: Path, dest: Path) -> Iterator[Path]:
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
    Path
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
    device: Path, mount_dir: Path, compression: Optional[ValidCompressions] = None
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
    """Close a decrypted device

    This function will try to close a device that was previously opened by
    `cryptsetup`. The given path must point into `/dev/mapper`, because
    `cryptsetup` always opens devices into there. If the given path points
    somewhere else, a InvalidDecryptedDevice is raised.

    Parameters:
    -----------
    device
        The device do be closed.

    Raises:
    -------
    InvalidDecryptedDevice
        if `device` does not point into `/dev/mapper`
    CalledProcessError
        if the exit code of the close command is non-zero
    """
    if device.parent != Path("/dev/mapper"):
        raise InvalidDecryptedDevice
    map_name = device.name
    close_cmd = ["sudo", "cryptsetup", "close", map_name]
    sh.run_cmd(cmd=close_cmd)


def encrypt_device(
    device: Path, password_cmd: str, *, fast_and_unsecure: bool = False
) -> UUID:
    """Encrypt a device

    This function will encrypt a device. The device can be any valid file-like
    object like real devices in `/dev/` or suitably sized files in $HOME.

    In order to retrieve the necessary password, the input `password_cmd` is
    executed in a subshell and its STDOUT used as password. Therefore, DO NOT
    USE UNTRUSTED `password_cmd`!

    The argument `fast_and_unsecure` is for internal use only. If set to
    `True`, `cryptsetup`'s PBKDF is configured to be as fast as possible. This
    renders it useless for any real-world use cases but is extremely helpful in
    the test suite.

    In order to obtain a safe password_cmd, refer to `generate_passcmd`.

    Parameters:
    -----------
    device
        file-like object to be encrypted
    password_cmd
        Shell command that prints the password to be used to STDOUT
    fast_and_unsecure
        for internal use only

    Returns:
    --------
    UUID
        UUID of the new LUKS partition
    """
    new_uuid = uuid4()
    format_cmd: sh.StrPathList = [
        "sudo",
        "cryptsetup",
        "luksFormat",
        "--uuid",
        str(new_uuid),
        device,
    ]
    if fast_and_unsecure:
        format_cmd.extend(
            [
                "--pbkdf-force-iterations",
                "4",
                "--pbkdf-memory",
                "32",
                "--pbkdf-parallel",
                "1",
            ]
        )

    sh.pipe_pass_cmd_to_real_cmd(pass_cmd=password_cmd, command=format_cmd)
    return new_uuid


def mkfs_btrfs(device: Path) -> None:
    """Format device with BtrFS

    Parameters:
    -----------
    device
        file-like object to be formatted
    """

    cmd: sh.StrPathList = ["sudo", "mkfs.btrfs", device]
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


def chown(
    file_or_folder: Path,
    /,
    user: Union[int, str],
    group: Optional[Union[int, str]] = None,
    *,
    recursive: bool,
) -> None:
    """Change user and group of a device or folder

    This function will change the ownership as specified. It requires root
    privileges and will ask for them if not available. If no group is given,
    only the owner is changed.

    If recursive is true, ownership information of all files and folders
    contained by `file_or_folder` will be adapted.

    If `file_or_folder` points to a file, `recursive` must be `False`.
    Otherwise a ValueError will be raised.


    Parameters:
    -----------
    user
        user ID, either as name or as UID
    group
        group ID, either as name or as GID
    recursive
        whether or not to change ownership for content

    Raises:
    --------
    ValueError
        if `file_or_folder` is a file but `recursive` is `True`
    """
    if file_or_folder.is_file() and recursive:
        raise ValueError(
            "First argument must point to a directory if `recursive` is `True`!"
        )

    user_spec = str(user) if group is None else f"{user}:{group}"
    chown_cmd: sh.StrPathList = ["sudo", "chown", user_spec, file_or_folder]
    if recursive is not None:
        chown_cmd.append("--recursive")
    sh.run_cmd(cmd=chown_cmd)
