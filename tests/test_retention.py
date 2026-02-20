from datetime import datetime, timedelta
from os.path import join

import pytest

from hfbr.retention import FileInfo, RetentionPlan, SlotOfRetention, parse_duration

# ── parse_duration ──────────────────────────────────────────────────────────


class TestParseDuration:
    def test_none_passthrough(self):
        assert parse_duration(None) is None

    def test_year_passthrough(self):
        assert parse_duration("year") == "year"

    def test_month_passthrough(self):
        assert parse_duration("month") == "month"

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("1 week", timedelta(weeks=1)),
            ("2 weeks", timedelta(weeks=2)),
            ("5 days", timedelta(days=5)),
            ("1 day", timedelta(days=1)),
            ("3 hours", timedelta(hours=3)),
            ("1 hour", timedelta(hours=1)),
            ("30 minutes", timedelta(minutes=30)),
            ("1 minute", timedelta(minutes=1)),
            ("45 seconds", timedelta(seconds=45)),
            ("1 second", timedelta(seconds=1)),
        ],
    )
    def test_valid_durations(self, value, expected):
        assert parse_duration(value) == expected

    def test_case_insensitive(self):
        assert parse_duration("1 Week") == timedelta(weeks=1)
        assert parse_duration("2 DAYS") == timedelta(days=2)

    def test_leading_trailing_whitespace(self):
        assert parse_duration("  1 week  ") == timedelta(weeks=1)

    def test_invalid_duration_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("bogus")

    def test_invalid_unit_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("5 fortnights")

    def test_missing_number_raises(self):
        with pytest.raises(ValueError, match="Invalid duration"):
            parse_duration("days")


# ── FileInfo ────────────────────────────────────────────────────────────────


class TestFileInfo:
    def test_basic_properties(self, tmp_path):
        f = tmp_path / "snapshot.bz2"
        f.write_bytes(b"data")
        fi = FileInfo(str(tmp_path), "snapshot.bz2", [])
        assert fi.filename == join(str(tmp_path), "snapshot.bz2")
        assert fi.dirpath == str(tmp_path)
        assert fi.pinned is False
        assert isinstance(fi.when, datetime)

    def test_pinned(self, tmp_path):
        f = tmp_path / "snapshot.bz2"
        f.write_bytes(b"data")
        fi = FileInfo(str(tmp_path), "snapshot.bz2", ["snapshot.bz2"])
        assert fi.pinned is True

    def test_str(self, tmp_path):
        f = tmp_path / "snapshot.bz2"
        f.write_bytes(b"data")
        fi = FileInfo(str(tmp_path), "snapshot.bz2", [])
        s = str(fi)
        assert "snapshot.bz2" in s

    def test_reduce_prefers_pinned(self, tmp_path):
        f1 = tmp_path / "a.bz2"
        f2 = tmp_path / "b.bz2"
        f1.write_bytes(b"1")
        f2.write_bytes(b"2")
        pinned = FileInfo(str(tmp_path), "a.bz2", ["a.bz2"])
        unpinned = FileInfo(str(tmp_path), "b.bz2", [])
        assert pinned.reduce(unpinned) is pinned
        assert unpinned.reduce(pinned) is pinned

    def test_reduce_prefers_earliest_when_same_pinned(self, tmp_path):
        import os
        import time

        f1 = tmp_path / "old.bz2"
        f2 = tmp_path / "new.bz2"
        f1.write_bytes(b"1")
        f2.write_bytes(b"2")
        # Force different mtimes
        old_time = time.time() - 1000
        os.utime(str(f1), (old_time, old_time))
        fi_old = FileInfo(str(tmp_path), "old.bz2", [])
        fi_new = FileInfo(str(tmp_path), "new.bz2", [])
        assert fi_old.reduce(fi_new) is fi_old
        assert fi_new.reduce(fi_old) is fi_old


# ── SlotOfRetention ─────────────────────────────────────────────────────────


class TestSlotOfRetention:
    def test_none_granularity(self):
        slot = SlotOfRetention(None, 5)
        assert slot.granularity == 1
        assert slot.quantity == 5

    def test_year_granularity(self):
        slot = SlotOfRetention("year", 3)
        assert slot.granularity == "year"

    def test_month_granularity(self):
        slot = SlotOfRetention("month", 12)
        assert slot.granularity == "month"

    def test_timedelta_granularity(self):
        slot = SlotOfRetention(timedelta(hours=1), 24)
        assert slot.granularity == 3600

    def test_invalid_granularity_raises(self):
        with pytest.raises(ValueError):
            SlotOfRetention(42, 5)  # type: ignore[arg-type]

    def test_muster_pins_files(self, tmp_path):
        import os
        import time

        files = []
        base_time = time.time()
        for i in range(5):
            f = tmp_path / f"snap_{i}.bz2"
            f.write_bytes(b"x")
            t = base_time - (i * 86400)  # each one day apart
            os.utime(str(f), (t, t))
            files.append(FileInfo(str(tmp_path), f"snap_{i}.bz2", []))

        files.sort(key=lambda f: -f.timestamp)
        slot = SlotOfRetention(timedelta(days=1), 3)
        slot.muster(files)
        pinned = [f for f in files if f.pinned]
        assert len(pinned) == 3

    def test_muster_unlimited_quantity(self, tmp_path):
        import os
        import time

        files = []
        base_time = time.time()
        for i in range(5):
            f = tmp_path / f"snap_{i}.bz2"
            f.write_bytes(b"x")
            t = base_time - (i * 86400)
            os.utime(str(f), (t, t))
            files.append(FileInfo(str(tmp_path), f"snap_{i}.bz2", []))

        files.sort(key=lambda f: -f.timestamp)
        slot = SlotOfRetention(timedelta(days=1), None)
        slot.muster(files)
        pinned = [f for f in files if f.pinned]
        assert len(pinned) == 5

    def test_calc_year(self, tmp_path):
        f = tmp_path / "a.bz2"
        f.write_bytes(b"x")
        fi = FileInfo(str(tmp_path), "a.bz2", [])
        slot = SlotOfRetention("year", 5)
        result = slot._calc_year(fi)
        assert result == fi.when.year

    def test_calc_month(self, tmp_path):
        f = tmp_path / "a.bz2"
        f.write_bytes(b"x")
        fi = FileInfo(str(tmp_path), "a.bz2", [])
        slot = SlotOfRetention("month", 12)
        result = slot._calc_month(fi)
        assert result == fi.when.year * 12 + fi.when.month

    def test_calc_secdiv(self, tmp_path):
        f = tmp_path / "a.bz2"
        f.write_bytes(b"x")
        fi = FileInfo(str(tmp_path), "a.bz2", [])
        slot = SlotOfRetention(timedelta(hours=1), 24)
        result = slot._calc_secdiv(fi)
        assert result == int(fi.timestamp / 3600)


# ── RetentionPlan ───────────────────────────────────────────────────────────


class TestRetentionPlan:
    def test_empty_plan_keeps_all(self, tmp_path):
        f = tmp_path / "snap.bz2"
        f.write_bytes(b"x")
        plan = RetentionPlan()
        plan.prune(str(tmp_path))
        assert f.exists()

    def test_plan_with_no_limited_slots_keeps_all(self, tmp_path):
        f = tmp_path / "snap.bz2"
        f.write_bytes(b"x")
        plan = RetentionPlan(((timedelta(days=1), None),))
        plan.prune(str(tmp_path))
        assert f.exists()

    def test_prune_dry_run(self, tmp_path):
        import os
        import time

        base_time = time.time()
        for i in range(10):
            f = tmp_path / f"snap_{i}.bz2"
            f.write_bytes(b"x")
            t = base_time - (i * 86400)
            os.utime(str(f), (t, t))

        plan = RetentionPlan(((timedelta(days=1), 3),))
        plan.prune(str(tmp_path), prune=False)
        # All files still exist (dry run)
        assert len(list(tmp_path.glob("*.bz2"))) == 10

    def test_prune_deletes_files(self, tmp_path):
        import os
        import time

        base_time = time.time()
        for i in range(10):
            f = tmp_path / f"snap_{i}.bz2"
            f.write_bytes(b"x")
            t = base_time - (i * 86400)
            os.utime(str(f), (t, t))

        plan = RetentionPlan(((timedelta(days=1), 3),))
        plan.prune(str(tmp_path), prune=True)
        remaining = list(tmp_path.glob("*.bz2"))
        assert len(remaining) == 3

    def test_prune_respects_pinned_list(self, tmp_path):
        import os
        import time

        base_time = time.time()
        for i in range(5):
            f = tmp_path / f"snap_{i}.bz2"
            f.write_bytes(b"x")
            t = base_time - (i * 86400)
            os.utime(str(f), (t, t))

        plan = RetentionPlan(((timedelta(days=1), 2),))
        plan.prune(str(tmp_path), pinned_list=["snap_4.bz2"], prune=True)
        remaining = sorted(f.name for f in tmp_path.glob("*.bz2"))
        assert "snap_4.bz2" in remaining

    def test_default_plan_is_empty(self):
        plan = RetentionPlan()
        assert plan.plan == ()
