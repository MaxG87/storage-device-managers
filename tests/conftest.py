from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest
import shell_interface as sh

import storage_device_managers as sdm


def get_random_filename(dir_: str) -> str:
    with NamedTemporaryFile(dir=dir_) as ntf:
        pass
    return ntf.name


@pytest.fixture
def mounted_directories():
    with TemporaryDirectory() as src:
        with TemporaryDirectory() as mountpoint:
            sh.run_cmd(cmd=["sudo", "mount", "-o", "bind", src, mountpoint])
            yield Path(src), Path(mountpoint)
            sh.run_cmd(cmd=["sudo", "umount", mountpoint])


@pytest.fixture
def big_file():
    min_size = 128 * 1024**2  # ~109MiB is the minimum size for BtrFS
    with TemporaryDirectory() as tempdir:
        filename = get_random_filename(dir_=tempdir)
        file = Path(filename)
        with file.open("wb") as fh:
            fh.write(bytes(min_size))
        yield file


@pytest.fixture
def encrypted_btrfs_device(big_file):
    """
    Create encrypted BtrFS file system

    Returns
    -------
    Path
        destination of encrypted BtrFS file system
    str
        password command that echos password to STDOUT
    """
    password_cmd = sdm.generate_passcmd()
    sdm.encrypt_device(big_file, password_cmd, fast_and_insecure=True)
    with sdm.decrypted_device(big_file, password_cmd) as decrypted:
        sdm.mkfs_btrfs(decrypted)
    return big_file, password_cmd


@pytest.fixture(params=["encrypted_btrfs_device"])
def encrypted_device(request):
    # As of now, the fixture seems superfluous. However, it is kept in case
    # support for other file systems is added later on.
    dest, pass_cmd = request.getfixturevalue(request.param)
    return dest, pass_cmd


@pytest.fixture
def btrfs_device(encrypted_btrfs_device):
    device, pass_cmd = encrypted_btrfs_device
    with sdm.decrypted_device(device, pass_cmd) as decrypted:
        yield decrypted
