[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)
[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg)](http://www.gnu.org/licenses/gpl-3.0)

# Storage Device Managers - Helpful context managers for managing decryption and mounts of storage devices

## Overview

The `storage_device_managers` module provides a set of utilities to manage
encrypted storage devices, handle BtrFS mounts, and perform file system
operations in a secure and structured way. It is designed to support common
storage-related tasks such as:

- Decrypting and mounting encrypted devices
- Managing BtrFS compression settings
- Creating and removing symbolic links with root privileges
- Formatting and encrypting devices
- Changing file ownership securely

## Features

- **Device Decryption & Encryption**: Easily decrypt and encrypt storage devices using `cryptsetup`.
- **BtrFS Mount Management**: Mount and unmount BtrFS file systems with optional compression settings.
- **Symbolic Link Handling**: Create and remove symbolic links with elevated permissions.
- **File System Operations**: Format devices with BtrFS, manage ownership, and check mount status.
- **Secure Passphrase Handling**: Automatically generate safe passwords for encryption.

## Usage

### Decrypting and Mounting a Device
```python
from pathlib import Path
from storage_device_managers import decrypted_device, mounted_device

# Decrypt and mount a device
with decrypted_device(Path("/dev/sdb1"), "cat /path/to/password-file") as dev:
    with mounted_device(dev) as mount_point:
        print(f"Device mounted at {mount_point}")
```

### Encrypting a Device
```python
from pathlib import Path
from storage_device_managers import encrypt_device

uuid = encrypt_device(Path("/dev/sdb1"), "cat /path/to/password-file")
print(f"Device encrypted with UUID: {uuid}")
```

### Creating a Symbolic Link
```python
from pathlib import Path
from storage_device_managers import symbolic_link

src = Path("/path/to/source")
dest = Path("/path/to/destination")

with symbolic_link(src, dest) as link:
    print(f"Symbolic link created at {link}")
```

## API Reference

### Context Managers
- `decrypted_device(device: Path, pass_cmd: str) -> Iterator[Path]`
  - Decrypts a device using `cryptsetup` and returns a context-managed path.
- `mounted_device(device: Path, compression: Optional[ValidCompressions] = None) -> Iterator[Path]`
  - Mounts a BtrFS device with optional compression settings.
- `symbolic_link(src: Path, dest: Path) -> Iterator[Path]`
  - Creates and removes a symbolic link with root privileges.

### Utility Functions
- `mount_btrfs_device(device: Path, mount_dir: Path, compression: Optional[ValidCompressions] = None) -> None`
- `is_mounted(device: Path) -> bool`
- `get_mounted_devices() -> Mapping[str, Mapping[Path, frozenset[str]]]`
- `unmount_device(device: Path) -> None`
- `open_encrypted_device(device: Path, pass_cmd: str) -> Path`
- `close_decrypted_device(device: Path) -> None`
- `encrypt_device(device: Path, password_cmd: str) -> UUID`
- `mkfs_btrfs(device: Path) -> None`
- `generate_passcmd() -> str`
- `chown(file_or_folder: Path, user: Union[int, str], group: Optional[Union[int, str]] = None, *, recursive: bool) -> None`

## Contributing
Contributions are welcome! Please submit issues and pull requests via GitHub.
