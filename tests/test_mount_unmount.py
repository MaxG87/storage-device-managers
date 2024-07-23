from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import storage_device_managers as sdm


def in_docker_container() -> bool:
    return Path("/.dockerenv").exists()


class MyCustomTestException(Exception):
    pass


@pytest.mark.parametrize(
    "args,kwargs",
    [
        ([], {}),
        ([sdm.ValidCompressions.ZSTD9], {}),
        ([sdm.ValidCompressions.ZLIB5, 0], {}),
        ([], {"subvol": "@"}),
        ([], {"subvol": 0}),
    ],
)
def test_mounted_device(btrfs_device, args, kwargs) -> None:
    with sdm.mounted_device(btrfs_device, *args, **kwargs) as md:
        assert md.exists()
        assert md.is_dir()
        assert sdm.is_mounted(btrfs_device)
        assert md in sdm.get_mounted_devices()[str(btrfs_device)]
    assert not md.exists()
    assert not sdm.is_mounted(btrfs_device)
    assert str(btrfs_device) not in sdm.get_mounted_devices()


def test_mounted_device_takes_over_already_mounted_device(btrfs_device) -> None:
    compression = sdm.ValidCompressions.LZO
    with TemporaryDirectory() as td:
        sdm.mount_btrfs_device(btrfs_device, Path(td), compression)
        with sdm.mounted_device(btrfs_device, compression) as md:
            assert sdm.is_mounted(btrfs_device)
            assert md in sdm.get_mounted_devices()[str(btrfs_device)]
        assert not sdm.is_mounted(btrfs_device)


@pytest.mark.skipif(
    in_docker_container(), reason="Root file system may be missing in Docker container."
)
def test_mounted_device_fails_on_not_unmountable_device() -> None:
    def get_root_device() -> Path:
        for device, mount_points in sdm.get_mounted_devices().items():
            if Path("/") in mount_points:
                return Path(device)
        raise ValueError("No device mounted on / was found.")

    root = get_root_device()
    with pytest.raises(sdm.UnmountError):
        with sdm.mounted_device(root):
            pass


def test_mounted_device_unmounts_in_case_of_exception(btrfs_device) -> None:
    with pytest.raises(MyCustomTestException):
        with sdm.mounted_device(btrfs_device, sdm.ValidCompressions.ZLIB1) as md:
            # That the device is mounted properly is guaranteed by a test
            # above.
            raise MyCustomTestException
    assert not md.exists()
    assert not sdm.is_mounted(btrfs_device)
    assert str(btrfs_device) not in sdm.get_mounted_devices()


@pytest.mark.parametrize("device", sdm.get_mounted_devices())
def test_is_mounted_detects(device: Path) -> None:
    assert sdm.is_mounted(device)


def test_is_mounted_rejects() -> None:
    with TemporaryDirectory() as tempd:
        assert not sdm.is_mounted(Path(tempd))


def test_unmount_device(btrfs_device) -> None:
    with TemporaryDirectory() as mountpoint:
        sdm.mount_btrfs_device(btrfs_device, Path(mountpoint))
        sdm.unmount_device(btrfs_device)
        assert not sdm.is_mounted(btrfs_device)


def test_unmount_device_raises_unmounterror() -> None:
    with TemporaryDirectory() as mountpoint:
        with pytest.raises(sdm.UnmountError):
            sdm.unmount_device(Path(mountpoint))
