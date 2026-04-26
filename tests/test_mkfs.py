from __future__ import annotations

import storage_device_managers as sdm


def test_mkfs_ext4(big_file) -> None:
    sdm.mkfs_ext4(big_file)
    assert sdm.get_filesystem(big_file) == "ext4"
