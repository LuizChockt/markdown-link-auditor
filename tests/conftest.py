from collections.abc import Callable, Mapping
from pathlib import Path

import pytest


@pytest.fixture
def make_vault(tmp_path: Path) -> Callable[[Mapping[str, str | bytes]], Path]:
    def create(files: Mapping[str, str | bytes]) -> Path:
        root = tmp_path / "vault"
        root.mkdir(exist_ok=True)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        return root

    return create


@pytest.fixture
def make_symlink() -> Callable[[Path, Path], None]:
    def create(link: Path, target: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (OSError, NotImplementedError):
            pytest.skip("Creating symlinks is unavailable for this OS/account.")

    return create
