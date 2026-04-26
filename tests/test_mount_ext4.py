from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import storage_device_managers as sdm


def test_mount_ext4_device(ext4_device) -> None:
    with TemporaryDirectory() as mount_dir:
        mount_path = Path(mount_dir)
        sdm.mount_ext4_device(ext4_device, mount_path)
        assert sdm.is_mounted(ext4_device)
        assert mount_path in sdm.get_mounted_devices()[str(ext4_device)]
        sdm.unmount_device(ext4_device)
        assert not sdm.is_mounted(ext4_device)


def test_mount_device_btrfs(btrfs_device) -> None:
    with TemporaryDirectory() as mount_dir:
        mount_path = Path(mount_dir)
        sdm.mount_device(btrfs_device, mount_path)
        assert sdm.is_mounted(btrfs_device)
        assert mount_path in sdm.get_mounted_devices()[str(btrfs_device)]
        sdm.unmount_device(btrfs_device)
        assert not sdm.is_mounted(btrfs_device)


def test_mount_device_ext4(ext4_device) -> None:
    with TemporaryDirectory() as mount_dir:
        mount_path = Path(mount_dir)
        sdm.mount_device(ext4_device, mount_path)
        assert sdm.is_mounted(ext4_device)
        assert mount_path in sdm.get_mounted_devices()[str(ext4_device)]
        sdm.unmount_device(ext4_device)
        assert not sdm.is_mounted(ext4_device)
