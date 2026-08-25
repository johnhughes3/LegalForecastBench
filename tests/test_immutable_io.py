from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from legalforecast import immutable_io


def test_private_directory_rejects_symlink_and_open_permissions(
    tmp_path: Path,
) -> None:
    created = immutable_io.ensure_private_directory(tmp_path / "created")
    assert created.stat().st_mode & 0o777 == 0o700

    open_directory = tmp_path / "open"
    open_directory.mkdir(mode=0o755)
    with pytest.raises(immutable_io.ImmutableIOError, match="owner-only"):
        immutable_io.ensure_private_directory(open_directory)

    actual = tmp_path / "actual"
    actual.mkdir(mode=0o700)
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    with pytest.raises(immutable_io.ImmutableIOError, match="unsafe"):
        immutable_io.ensure_private_directory(linked)


def test_single_link_read_rejects_symlink_and_hardlink(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_bytes(b"{}\n")
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(source)

    with pytest.raises(immutable_io.ImmutableIOError, match="cannot read symlink"):
        immutable_io.read_single_link_file(symlink, label="symlink")

    hardlink = tmp_path / "hardlink.json"
    os.link(source, hardlink)
    with pytest.raises(immutable_io.ImmutableIOError, match="one link"):
        immutable_io.read_single_link_file(source, label="source")
    with pytest.raises(immutable_io.ImmutableIOError, match="one link"):
        immutable_io.read_single_link_file(hardlink, label="hardlink")


def test_single_link_read_rejects_symlinked_parent(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "source.json").write_bytes(b"{}\n")
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(actual, target_is_directory=True)

    with pytest.raises(immutable_io.ImmutableIOError, match="parent is unsafe"):
        immutable_io.read_single_link_file(
            linked_parent / "source.json", label="source"
        )


def test_create_only_tree_publishes_exact_members(tmp_path: Path) -> None:
    root = tmp_path / "published"

    immutable_io.publish_tree_create_only(
        root,
        {"a.json": b"a\n", "nested/b.json": b"b\n"},
    )

    assert (root / "a.json").read_bytes() == b"a\n"
    assert (root / "nested/b.json").read_bytes() == b"b\n"
    with pytest.raises(immutable_io.ImmutableIOError, match="already exists"):
        immutable_io.publish_tree_create_only(root, {"other.json": b"x\n"})


def test_create_only_tree_applies_validated_file_modes(tmp_path: Path) -> None:
    root = tmp_path / "published-modes"

    immutable_io.publish_tree_create_only(
        root,
        {"private.txt": b"private\n", "index.json": b"{}\n"},
        file_modes={"private.txt": 0o400, "index.json": 0o600},
    )

    assert stat.S_IMODE((root / "private.txt").stat().st_mode) == 0o400
    assert stat.S_IMODE((root / "index.json").stat().st_mode) == 0o600

    with pytest.raises(immutable_io.ImmutableIOError, match="unknown payloads"):
        immutable_io.publish_tree_create_only(
            tmp_path / "unknown-mode",
            {"index.json": b"{}\n"},
            file_modes={"missing.txt": 0o400},
        )
    with pytest.raises(immutable_io.ImmutableIOError, match="0400 or 0600"):
        immutable_io.publish_tree_create_only(
            tmp_path / "open-mode",
            {"index.json": b"{}\n"},
            file_modes={"index.json": 0o644},
        )
    assert not (tmp_path / "unknown-mode").exists()
    assert not (tmp_path / "open-mode").exists()


def test_create_only_tree_rejects_missing_parent_without_mutation(
    tmp_path: Path,
) -> None:
    missing_parent = tmp_path / "missing"

    with pytest.raises(immutable_io.ImmutableIOError, match="output parent is unsafe"):
        immutable_io.publish_tree_create_only(
            missing_parent / "published", {"a.json": b"a\n"}
        )

    assert not missing_parent.exists()


def test_create_only_tree_cleans_staging_directory_after_lost_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "published"

    def lose_race(
        _parent_fd: int,
        _source_name: str,
        _destination_name: str,
        path: Path,
    ) -> None:
        root.mkdir()
        raise FileExistsError(path)

    monkeypatch.setattr(immutable_io, "_rename_noreplace_at", lose_race)

    with pytest.raises(immutable_io.ImmutableIOError, match="already exists"):
        immutable_io.publish_tree_create_only(root, {"nested/a.json": b"a\n"})

    assert list(tmp_path.iterdir()) == [root]


def test_create_only_write_rejects_symlinked_parent(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(actual, target_is_directory=True)

    with pytest.raises(immutable_io.ImmutableIOError, match="output parent is unsafe"):
        immutable_io.write_file_create_only(linked_parent / "output.json", b"{}\n")

    assert not (actual / "output.json").exists()


def test_create_only_write_rejects_missing_parent_without_mutation(
    tmp_path: Path,
) -> None:
    missing_parent = tmp_path / "missing"

    with pytest.raises(immutable_io.ImmutableIOError, match="output parent is unsafe"):
        immutable_io.write_file_create_only(missing_parent / "output.json", b"{}\n")

    assert not missing_parent.exists()


def test_safe_replace_refuses_symlink_and_hardlink_targets(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_bytes(b"sentinel\n")
    symlink = tmp_path / "symlink.json"
    symlink.symlink_to(outside)

    with pytest.raises(immutable_io.ImmutableIOError, match="regular file"):
        immutable_io.write_file_replace_safe(symlink, b"replaced\n")
    assert outside.read_bytes() == b"sentinel\n"

    hardlink = tmp_path / "hardlink.json"
    os.link(outside, hardlink)
    with pytest.raises(immutable_io.ImmutableIOError, match="single-link"):
        immutable_io.write_file_replace_safe(hardlink, b"replaced\n")
    assert outside.read_bytes() == b"sentinel\n"


def test_safe_replace_creates_and_replaces_owner_file(tmp_path: Path) -> None:
    output = tmp_path / "output.json"

    immutable_io.write_file_replace_safe(output, b"first\n")
    immutable_io.write_file_replace_safe(output, b"second\n")

    assert output.read_bytes() == b"second\n"
    assert output.stat().st_mode & 0o777 == 0o600


def test_create_only_tree_rejects_symlinked_parent_without_mutation(
    tmp_path: Path,
) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(actual, target_is_directory=True)

    with pytest.raises(immutable_io.ImmutableIOError, match="output parent is unsafe"):
        immutable_io.publish_tree_create_only(
            linked_parent / "published", {"nested/a.json": b"a\n"}
        )

    assert not (actual / "published").exists()
    assert list(actual.iterdir()) == []


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape"])
def test_create_only_tree_rejects_unsafe_members(tmp_path: Path, name: str) -> None:
    with pytest.raises(immutable_io.ImmutableIOError, match="unsafe output member"):
        immutable_io.publish_tree_create_only(tmp_path / "published", {name: b"x"})
    assert not any(tmp_path.iterdir())
