from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import shell_interface as sh

import storage_device_managers as sdm


@pytest.fixture
def directory_with_content(tmp_path):
    subfolder = tmp_path / "subfolder"
    mkdir_cmd: sh.StrPathList = ["sudo", "mkdir", subfolder]
    sh.run_cmd(cmd=mkdir_cmd)

    file = tmp_path / "important-file"
    touch_cmd: sh.StrPathList = ["sudo", "touch", file]
    sh.run_cmd(cmd=touch_cmd)

    yield tmp_path, file
    rm_cmd: sh.StrPathList = ["sudo", "rm", "-r", subfolder]
    sh.run_cmd(cmd=rm_cmd)


def test_chown_raises_valueerror():
    with pytest.raises(ValueError, match="directory.*recursive"):
        with NamedTemporaryFile() as temp_file:
            file = Path(temp_file.name)
            sdm.chown(file, file.owner(), recursive=True)


def test_chown_file(directory_with_content):
    _, file = directory_with_content
    assert file.owner() == "root"
    expected_user = sh.get_user()
    sdm.chown(file, expected_user, recursive=False)
    result_user = file.owner()
    assert result_user == expected_user


def test_chown_recursive(directory_with_content):
    directory, _ = directory_with_content
    all_files_and_folders = list(directory.rglob("*"))

    initial_owners = {cur.owner() for cur in all_files_and_folders}
    initial_group = {cur.group() for cur in all_files_and_folders}
    assert initial_owners == {"root"}
    assert initial_group == {"root"}

    expected_user = sh.get_user()
    expected_group = sh.get_group(expected_user)
    sdm.chown(directory, expected_user, expected_group, recursive=False)

    result_users = {cur.owner() for cur in all_files_and_folders}
    result_group = {cur.group() for cur in all_files_and_folders}
    assert result_users == {expected_user}
    assert result_group == {expected_group}
