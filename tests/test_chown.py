from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import shell_interface as sh

import storage_device_managers as sdm


@pytest.fixture
def mounted_device_with_content(btrfs_device):
    with sdm.mounted_device(btrfs_device) as mounted:
        subfolder = mounted / "subfolder"
        mkdir_cmd: sh.StrPathList = ["sudo", "mkdir", subfolder]
        sh.run_cmd(cmd=mkdir_cmd)

        file = subfolder / "important-file"
        touch_cmd: sh.StrPathList = ["sudo", "touch", file]
        sh.run_cmd(cmd=touch_cmd)
        yield mounted, file


def test_chown_raises_valueerror():
    with pytest.raises(ValueError, match="directory.*recursive"):
        with NamedTemporaryFile() as temp_file:
            file = Path(temp_file.name)
            sdm.chown(file, file.owner(), recursive=True)


def test_chown_file(mounted_device_with_content):
    device, file = mounted_device_with_content
    assert file.owner() == "root"
    expected_user = sh.get_user()
    sdm.chown(file, expected_user, recursive=False)
    result_user = file.owner()
    assert result_user == expected_user


def test_chown_recursive(mounted_device_with_content):
    device, _ = mounted_device_with_content
    all_files_and_folders = list(device.rglob("*"))

    initial_owners = {cur.owner() for cur in all_files_and_folders}
    initial_group = {cur.group() for cur in all_files_and_folders}
    assert initial_owners == {"root"}
    assert initial_group == {"root"}

    expected_user = sh.get_user()
    expected_group = sh.get_group(expected_user)
    sdm.chown(device, expected_user, expected_group, recursive=False)

    result_users = {cur.owner() for cur in all_files_and_folders}
    result_group = {cur.group() for cur in all_files_and_folders}
    assert result_users == {expected_user}
    assert result_group == {expected_group}
