from __future__ import annotations

import os
import subprocess
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from uuid import UUID

import pytest
import shell_interface as sh
from hypothesis import given
from hypothesis import strategies as st

import storage_device_managers as sdm


def get_random_filename() -> str:
    with NamedTemporaryFile() as named_file:
        return named_file.name


class MyCustomTestException(Exception):
    pass


def test_mounted_device_without_compression(btrfs_device) -> None:
    with sdm.mounted_device(btrfs_device) as md:
        assert md.exists()
        assert md.is_dir()
        assert sdm.is_mounted(btrfs_device)
        assert md in sdm.get_mounted_devices()[str(btrfs_device)]
    assert not md.exists()
    assert not sdm.is_mounted(btrfs_device)
    assert str(btrfs_device) not in sdm.get_mounted_devices()


def test_mounted_device_with_compression(btrfs_device) -> None:
    with sdm.mounted_device(btrfs_device, sdm.ValidCompressions.ZSTD9) as md:
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


def test_mounted_device_fails_on_not_unmountable_device() -> None:
    def get_root_device() -> Path:
        for device, mount_points in sdm.get_mounted_devices().items():
            if Path("/") in mount_points:
                return Path(device)
        raise ValueError("No device mounted on / was found.")

    root = get_root_device()
    with pytest.raises(subprocess.CalledProcessError):
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


def test_get_mounted_devices_raises_on_unknown_device() -> None:
    with pytest.raises(KeyError):
        sdm.get_mounted_devices()["unknown-device"]


def test_get_mounted_devices_includes_correct_mountpoints(mounted_directories) -> None:
    src, dest = mounted_directories
    assert any(
        dest in mount_points for mount_points in sdm.get_mounted_devices().values()
    )


def test_get_mounted_devices_includes_root() -> None:
    assert any(Path("/") in dest_set for dest_set in sdm.get_mounted_devices().values())


def test_unmount_device(btrfs_device) -> None:
    with TemporaryDirectory() as mountpoint:
        sdm.mount_btrfs_device(btrfs_device, Path(mountpoint))
        sdm.unmount_device(btrfs_device)
        assert not sdm.is_mounted(btrfs_device)


def test_decrypt_device_roundtrip(encrypted_device) -> None:
    device, pass_cmd = encrypted_device
    decrypted = sdm.open_encrypted_device(device=device, pass_cmd=pass_cmd)
    assert decrypted.exists()
    assert decrypted.name == device.name
    sdm.close_decrypted_device(device=decrypted)
    assert not decrypted.exists()


@given(uuid=st.uuids())
def test_close_decrypted_device_rejects_invalid_device_name(uuid) -> None:
    with TemporaryDirectory() as td:
        device = Path(td) / str(uuid)
        with pytest.raises(sdm.InvalidDecryptedDevice):
            sdm.close_decrypted_device(device)


def test_decrypted_device(encrypted_device) -> None:
    device, pass_cmd = encrypted_device
    with sdm.decrypted_device(device=device, pass_cmd=pass_cmd) as dd:
        assert dd.exists()
    assert not dd.exists()


def test_decrypted_device_closes_in_case_of_exception(encrypted_device) -> None:
    device, pass_cmd = encrypted_device
    with pytest.raises(MyCustomTestException):
        with sdm.decrypted_device(device=device, pass_cmd=pass_cmd) as dd:
            raise MyCustomTestException
    assert not dd.exists()


def test_decrypted_device_can_use_home_for_passcmd(encrypted_device) -> None:
    # Regression Test
    # Test if `decrypted_device` can use a program that is located in PATH. For
    # some reason, when passing `{}` as environment, `echo` works, but `pass`
    # did not. This test ensures that the necessary fix is not reverted again.
    device, pass_cmd = encrypted_device
    passphrase = pass_cmd.split()[-1]
    relative_home = Path("~")  # must be relative to trigger regression
    with NamedTemporaryFile(dir=relative_home.expanduser()) as pwd_f:
        absolute_pwd_f = Path(pwd_f.name)
        relative_pwd_f = relative_home / absolute_pwd_f.name
        absolute_pwd_f.write_text(passphrase)
        with sdm.decrypted_device(
            device=device, pass_cmd=f"cat {relative_pwd_f}"
        ) as dd:
            assert dd.exists()
        assert not dd.exists()


def test_symbolic_link_rejects_existing_dest(tmp_path: Path) -> None:
    with NamedTemporaryFile() as named_file:
        source = Path(named_file.name)
        with pytest.raises(FileExistsError):
            with sdm.symbolic_link(source, dest=tmp_path):
                pass


def test_symbolic_link_rejects_missing_src() -> None:
    src = Path(get_random_filename())
    dest = Path(get_random_filename())
    with pytest.raises(FileNotFoundError):
        with sdm.symbolic_link(src=src, dest=dest):
            pass


def test_symbolic_link() -> None:
    content = "some arbitrary content"
    with NamedTemporaryFile() as named_file:
        source = Path(named_file.name)
        source.write_text(content)
        in_dest = Path(get_random_filename())
        with sdm.symbolic_link(src=source, dest=in_dest) as out_dest:
            assert in_dest == out_dest
            assert out_dest.is_symlink()
            assert out_dest.read_bytes() == source.read_bytes()
        assert not out_dest.exists()


def test_symbolic_link_removes_link_in_case_of_exception() -> None:
    with pytest.raises(MyCustomTestException):
        with NamedTemporaryFile() as src_f:
            source = Path(src_f.name)
            dest_p = Path(get_random_filename())
            assert not os.path.lexists(dest_p)
            with sdm.symbolic_link(src=source, dest=dest_p):
                assert os.path.lexists(dest_p)
                raise MyCustomTestException
    assert not os.path.lexists(dest_p)


def test_symbolic_link_does_not_crash_in_case_of_vanished_link() -> None:
    content = "some arbitrary content"
    with NamedTemporaryFile() as named_file:
        source = Path(named_file.name)
        source.write_text(content)
        in_dest = Path(get_random_filename())
        with sdm.symbolic_link(src=source, dest=in_dest) as out_dest:
            cmd: sh.StrPathList = ["sudo", "rm", out_dest]
            sh.run_cmd(cmd=cmd)


def test_generate_passcmd_is_not_static():
    N = 128
    passwords = Counter(sdm.generate_passcmd() for _ in range(N))
    assert set(passwords.values()) == {1}


def test_generate_passcmd_samples_uniformly():
    # TODO: The bounds should be tightened. Finally, the test should have a
    # probability to fail one in ~100 runs or so.
    N = 128
    chars: Counter[str] = Counter()
    for _ in range(N):
        passcmd = sdm.generate_passcmd()
        passphrase = passcmd.split()[-1]
        chars.update(passphrase)

    nof_chars = sum(chars.values())
    expected_frequency = 1 / (26 + 26 + 10)
    lower_bound = 0.25 * expected_frequency
    upper_bound = 1.75 * expected_frequency
    assert all(len(char) == 1 for char in chars)
    assert all(lower_bound < (cur / nof_chars) < upper_bound for cur in chars.values())


def test_encrypt_device(big_file) -> None:
    pass_cmd = sdm.generate_passcmd()
    result_uuid = sdm.encrypt_device(big_file, pass_cmd)
    uuid_check_cmd = ["sudo", "cryptsetup", "luksUUID", big_file]
    uuid_check_proc = sh.run_cmd(cmd=uuid_check_cmd, capture_output=True)
    reported_uuid = UUID(uuid_check_proc.stdout.decode().strip())
    assert result_uuid == reported_uuid
