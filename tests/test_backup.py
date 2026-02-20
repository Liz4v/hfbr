import bz2
from hashlib import sha512
from io import BytesIO

from hfbr.backup import backup_and_retention, backup_target_database, block_transfer
from hfbr.retention import RetentionPlan


# ── block_transfer ──────────────────────────────────────────────────────────


class TestBlockTransfer:
    def test_copies_data(self):
        src = BytesIO(b"hello world")
        dst = BytesIO()
        block_transfer(src.read, dst.write)
        assert dst.getvalue() == b"hello world"

    def test_copies_large_data_in_chunks(self):
        data = b"x" * (32 * 1024 + 7)
        src = BytesIO(data)
        dst = BytesIO()
        block_transfer(src.read, dst.write, length=1024)
        assert dst.getvalue() == data

    def test_empty_source(self):
        src = BytesIO(b"")
        dst = BytesIO()
        block_transfer(src.read, dst.write)
        assert dst.getvalue() == b""


# ── backup_target_database ──────────────────────────────────────────────────


class TestBackupTargetDatabase:
    def test_first_backup_creates_snapshot_and_hash(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"database content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        backup_target_database(str(target), str(backup_dir))

        hash_path = backup_dir / "last_hash"
        assert hash_path.exists()
        expected_hash = sha512(b"database content").digest()
        assert hash_path.read_bytes() == expected_hash

        snapshots = list(backup_dir.glob("*.bz2"))
        assert len(snapshots) == 1
        assert bz2.decompress(snapshots[0].read_bytes()) == b"database content"

    def test_unchanged_file_no_new_snapshot(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"same content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Write the hash as if a previous backup already happened
        hash_path = backup_dir / "last_hash"
        hash_path.write_bytes(sha512(b"same content").digest())

        backup_target_database(str(target), str(backup_dir))

        snapshots = list(backup_dir.glob("*.bz2"))
        assert len(snapshots) == 0

    def test_changed_file_creates_new_snapshot(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"old content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        hash_path = backup_dir / "last_hash"
        hash_path.write_bytes(sha512(b"old content").digest())

        # Change the file
        target.write_bytes(b"new content")
        backup_target_database(str(target), str(backup_dir))

        snapshots = list(backup_dir.glob("*.bz2"))
        assert len(snapshots) == 1
        assert bz2.decompress(snapshots[0].read_bytes()) == b"new content"
        assert hash_path.read_bytes() == sha512(b"new content").digest()

    def test_snapshot_filename_has_extension(self, tmp_path):
        target = tmp_path / "data.sqlite"
        target.write_bytes(b"content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        backup_target_database(str(target), str(backup_dir))

        snapshots = list(backup_dir.glob("*.bz2"))
        assert len(snapshots) == 1
        assert ".sqlite.bz2" in snapshots[0].name


# ── backup_and_retention ────────────────────────────────────────────────────


class TestBackupAndRetention:
    def test_no_target_or_backup_dir_logs_error(self):
        # Should not raise, just log an error and return
        backup_and_retention(target_path=None, backup_dir=None)

    def test_with_target_path_only(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"content")

        backup_and_retention(target_path=str(target))

        # backup_dir defaults to dirname of target
        hash_path = tmp_path / "last_hash"
        assert hash_path.exists()

    def test_with_target_and_backup_dir(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        backup_and_retention(target_path=str(target), backup_dir=str(backup_dir))

        assert (backup_dir / "last_hash").exists()
        assert len(list(backup_dir.glob("*.bz2"))) == 1

    def test_with_retention_plan_tuple(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        backup_and_retention(target_path=str(target), backup_dir=str(backup_dir), retention_plan=())

    def test_with_retention_plan_object(self, tmp_path):
        target = tmp_path / "data.db"
        target.write_bytes(b"content")
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        plan = RetentionPlan()
        backup_and_retention(target_path=str(target), backup_dir=str(backup_dir), retention_plan=plan)

    def test_backup_dir_only_runs_retention(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        f = backup_dir / "snap.bz2"
        f.write_bytes(b"x")

        backup_and_retention(backup_dir=str(backup_dir), retention_plan=())
        # No crash, file still there
        assert f.exists()
