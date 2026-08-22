from __future__ import annotations

import os
from pathlib import Path

import pytest
from legalforecast import immutable_io


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


@pytest.mark.parametrize("name", ["../escape", "/absolute", "a/../../escape"])
def test_create_only_tree_rejects_unsafe_members(tmp_path: Path, name: str) -> None:
    with pytest.raises(immutable_io.ImmutableIOError, match="unsafe output member"):
        immutable_io.publish_tree_create_only(tmp_path / "published", {name: b"x"})
    assert not any(tmp_path.iterdir())
