#
# Copyright 2015-2026, Liz Balbuena
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.
#
from collections.abc import Sequence
from datetime import datetime, timedelta
from functools import reduce
from logging import getLogger
from os import listdir, unlink
from os.path import basename, getmtime, join
from re import compile as re_compile

log = getLogger(__name__)


class RetentionPlan:
    def __init__(self, plan_description: tuple[tuple[timedelta | str | None, int | None], ...] | None = None) -> None:
        self.plan = plan_description or ()

    def prune(self, target_dir: str = ".", pinned_list: Sequence[str] = (), prune: bool = False) -> None:
        if True not in [True for slot in self.plan if slot[1]]:  # at least one slot with limited quantity?
            log.info("No retention plan on %s. Keeping all files.", target_dir)
            return
        log.info("Applying retention plan to %s.", target_dir)
        files = [FileInfo(target_dir, f, pinned_list) for f in listdir(target_dir) if f.endswith(".bz2")]
        files.sort(key=lambda f: -f.timestamp)
        for granularity, quantity in self.plan:
            SlotOfRetention(granularity, quantity).muster(files)
        for file in files:
            if file.pinned:
                log.debug("Keep file " + str(file))
            else:
                log.info("Prune file " + str(file))
                if prune:
                    unlink(file.filename)


class FileInfo:
    def __init__(self, dirpath: str, filename: str, pinned_list: Sequence[str]) -> None:
        self.dirpath = dirpath
        self.filename = join(dirpath, filename)
        self.timestamp = getmtime(self.filename)
        self.when = datetime.fromtimestamp(self.timestamp)
        self.pinned = filename in pinned_list

    def __str__(self) -> str:
        return " ".join((self.when.strftime("%Y%m%d%H%M%S"), basename(self.filename)))

    def reduce(self, them: "FileInfo") -> "FileInfo":
        if self.pinned != them.pinned:
            return self if self.pinned > them.pinned else them
        else:
            return self if self.timestamp <= them.timestamp else them


DURATION_PATTERN = re_compile(r"^(\d+)\s*(weeks?|days?|hours?|minutes?|seconds?)$")


def parse_duration(value: str | None) -> timedelta | str | None:
    """Convert a human-readable duration string (e.g. '1 week') to a timedelta, or pass through 'year'/'month'/None."""
    if value is None or value in ("year", "month"):
        return value
    match = DURATION_PATTERN.match(str(value).strip().lower())
    if not match:
        raise ValueError(f"Invalid duration: {value!r}. Expected format like '1 week', '5 days', '1 hour'.")
    amount, unit = int(match.group(1)), match.group(2)
    if not unit.endswith("s"):
        unit += "s"
    return timedelta(**{unit: amount})


class SlotOfRetention:
    def __init__(self, granularity: timedelta | str | None, quantity: int | None) -> None:
        self.quantity = quantity
        if granularity is None:
            self.granularity: int | str = 1
            self._calc = self._calc_secdiv
        elif isinstance(granularity, str):
            self.granularity = granularity
            self._calc = getattr(self, "_calc_" + granularity)
        elif isinstance(granularity, timedelta):
            self.granularity = int(granularity.total_seconds())
            self._calc = self._calc_secdiv
        else:
            raise ValueError("Unknown granularity type %s", type(granularity))

    def muster(self, list_of_files: list[FileInfo]) -> None:
        timeslots: dict[int, list[FileInfo]] = {}
        for fileinfo in list_of_files:
            position = self._calc(fileinfo)
            if position not in timeslots:
                timeslots[position] = []
            timeslots[position].append(fileinfo)
        keys = sorted(timeslots.keys(), reverse=True)
        if self.quantity:
            keys = keys[: self.quantity]
        for slot in keys:
            chosen = reduce(FileInfo.reduce, timeslots[slot])
            chosen.pinned = True

    def _calc_secdiv(self, fileinfo: FileInfo) -> int:
        assert isinstance(self.granularity, int)
        return int(fileinfo.timestamp / self.granularity)

    def _calc_month(self, fileinfo: FileInfo) -> int:
        return int(fileinfo.when.year * 12 + fileinfo.when.month)

    def _calc_year(self, fileinfo: FileInfo) -> int:
        return fileinfo.when.year
