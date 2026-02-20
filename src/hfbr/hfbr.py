#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from bz2 import BZ2File
from datetime import datetime, timedelta
from functools import reduce
from hashlib import sha512
from logging import getLogger
from logging.config import dictConfig
from os import listdir, unlink
from os.path import abspath, basename, dirname, getmtime, isfile, join, splitext
from re import compile as re_compile
from sys import argv

from yaml import safe_load

log = getLogger("hfbr")


def main():
    settings = Settings()
    log.info("^" * 40)
    for item in settings:
        backup_and_retention(**item)
    log.info("v" * 40)


def backup_target_database(target_path, backup_dir):
    hash_path = join(backup_dir, "last_hash")
    hasher = sha512()
    with open(target_path, "rb") as target:
        block_transfer(target.read, hasher.update)
    try:
        with open(hash_path, "rb") as hashfile:
            old_hash = hashfile.read()
    except FileNotFoundError:
        old_hash = b""
    if hasher.digest() != old_hash:
        snapshot_filename = datetime.now().strftime("%Y%m%d-%H%M") + splitext(target_path)[1] + ".bz2"
        snapshot_path = join(backup_dir, snapshot_filename)
        log.debug("Change detected! Saving to %s", snapshot_path)
        with open(target_path, "rb") as target, BZ2File(snapshot_path, "wb") as snapshot:
            block_transfer(target.read, snapshot.write)
        with open(hash_path, "wb") as hashfile:
            hashfile.write(hasher.digest())


def block_transfer(fread, fwrite, length=16 * 1024):
    """Copy blocks using file-like reader and write functions, based on shutil.copyfileobj."""
    buffer = fread(length)
    while buffer:
        fwrite(buffer)
        buffer = fread(length)


class RetentionPlan:
    def __init__(self, plan_description=None):
        self.plan = plan_description or ()

    def prune(self, target_dir=".", pinned_list=(), prune=False):
        if True not in [True for slot in self.plan if slot[1]]:  # at least one slot with limited quantity?
            log.info("No retention plan on %s. Keeping all files.", target_dir)
            return
        log.info("Applying retention plan to %s.", target_dir)
        files = [FileInfo(target_dir, f, pinned_list) for f in listdir(target_dir) if f.endswith(".bz2")]
        files.sort(key=lambda f: -f.timestamp)
        for retention in [SlotOfRetention(*slot) for slot in self.plan]:
            retention.muster(files)
        for file in files:
            if file.pinned:
                log.debug("Keep file " + str(file))
            else:
                log.info("Prune file " + str(file))
                if prune:
                    unlink(file.filename)


class FileInfo(object):
    def __init__(self, dirpath, filename, pinned_list):
        self.dirpath = dirpath
        self.filename = join(dirpath, filename)
        self.timestamp = getmtime(self.filename)
        self.when = datetime.fromtimestamp(self.timestamp)
        self.pinned = filename in pinned_list

    def __str__(self):
        return " ".join((self.when.strftime("%Y%m%d%H%M%S"), basename(self.filename)))

    def reduce(self, them):
        if self.pinned != them.pinned:
            return self if self.pinned > them.pinned else them
        else:
            return self if self.timestamp <= them.timestamp else them


DURATION_PATTERN = re_compile(r"^(\d+)\s*(weeks?|days?|hours?|minutes?|seconds?)$")


def parse_duration(value):
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
    def __init__(self, granularity, quantity):
        self.quantity = quantity
        if granularity is None:
            self.granularity = 1
            self._calc = self._calc_secdiv
        elif isinstance(granularity, str):
            self.granularity = granularity
            self._calc = getattr(self, "_calc_" + granularity)
        elif isinstance(granularity, timedelta):
            self.granularity = int(granularity.total_seconds())
            self._calc = self._calc_secdiv
        else:
            raise ValueError("Unknown granularity type %s", type(granularity))

    def muster(self, list_of_files):
        timeslots = {}
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

    def _calc_secdiv(self, fileinfo: FileInfo):
        return int(fileinfo.timestamp / self.granularity)

    def _calc_month(self, fileinfo: FileInfo):
        return int(fileinfo.when.year * 12 + fileinfo.when.month)

    def _calc_year(self, fileinfo: FileInfo):
        return fileinfo.when.year


class Settings(list):
    def __init__(self):
        config = self._load_yaml() or {}
        if "logging" in config:
            dictConfig(config["logging"])
        super().__init__(config.get("targets") or list(self._targets_from_argv()))
        plans = {}
        for name, slots in config.get("plans", {}).items():
            plans[name] = RetentionPlan(tuple((parse_duration(s[0]), s[1]) for s in slots))
        for item in self:
            plan = item.get("retention_plan")
            if isinstance(plan, str):
                item["retention_plan"] = plans[plan]
            elif isinstance(plan, list):
                item["retention_plan"] = RetentionPlan(tuple((parse_duration(s[0]), s[1]) for s in plan))

    @staticmethod
    def _load_yaml():
        config_path = "settings.yaml"
        if not isfile(config_path):
            return None
        with open(config_path) as f:
            return safe_load(f)

    def _targets_from_argv(self):
        argv.pop(0)  # remove script name
        if not len(argv):
            log.fatal("Nothing to do! Check the documentation and make sure to have a settings file.")
            exit(1)
            return []
        target = {"target_path": argv.pop(0)}
        if len(argv):
            target["backup_dir"] = argv.pop(0)
        yield target


def backup_and_retention(target_path=None, backup_dir=None, retention_plan=(), pin=(), prune=True):
    if not (target_path or backup_dir):
        log.error("Invalid target: no target_path or backup_dir. Check your settings!")
        return
    if target_path:
        log.info("Applying backup plan: %s", target_path)
        if not backup_dir:
            backup_dir = dirname(abspath(target_path))
        backup_target_database(target_path, backup_dir)
    if not isinstance(retention_plan, RetentionPlan):
        retention_plan = RetentionPlan(retention_plan)
    retention_plan.prune(backup_dir, pin, prune)


if __name__ == "__main__":
    main()
