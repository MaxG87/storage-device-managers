from __future__ import annotations

from pathlib import Path

import pytest

import storage_device_managers as sdm


@pytest.fixture(params=["btrfs_device", "ext4_device"])
def device_with_fs(request) -> tuple[Path, sdm.ValidFileSystems]:
    filesystem = request.param.split("_")[0]
    return (request.getfixturevalue(request.param), filesystem)


def test_get_filesystem(device_with_fs) -> None:
    (device, expected_filesystem) = device_with_fs
    assert sdm.get_filesystem(device) == expected_filesystem
