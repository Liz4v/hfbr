#!/usr/bin/env python3
# coding=utf-8
#
# Copyright 2015, Ekevoo
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
from logging import getLogger
from logging.config import dictConfig
from os import listdir, unlink
from os.path import abspath, basename, dirname, getmtime, join, splitext
from hashlib import sha512
from sys import argv

log = getLogger('hfbrw')


def main():
    settings = Settings()
    log.info('^' * 40)
    for item in settings:
        backup_and_retention(**item)
    log.info('v' * 40)


def backup_target_database(target_path, backup_dir):
    hash_path = join(backup_dir, 'last_hash')
    hasher = sha512()
    with open(target_path, 'rb') as target:
        block_transfer(target.read, hasher.update)
    with open(hash_path, 'rb') as hashfile:
        old_hash = hashfile.read()
    if hasher.digest() != old_hash:
        snapshot_filename = datetime.now().strftime('%Y%m%d-%H%M') + splitext(target_path)[1] + '.bz2'
        log.debug('Change detected! Saving to %s', snapshot_filename)
        snapshot_path = join(backup_dir, snapshot_filename)
        with open(target_path, 'rb') as target, BZ2File(snapshot_path, 'wb') as snapshot:
            block_transfer(target.read, snapshot.write)
        with open(hash_path, 'wb') as hashfile:
            hashfile.write(hasher.digest())


def block_transfer(fread, fwrite, length=16 * 1024):
    """Copy blocks using file-like reader and write functions, based on shutil.copyfileobj."""
    buffer = fread(length)
    while buffer:
        fwrite(buffer)
        buffer = fread(length)


class RetentionPlan:
    def __init__(self, plan_description=((None, None),)):
        self.plan = plan_description

    def prune(self, target_dir='.', pinned_list=(), pretend=True):
        files = [FileInfo(target_dir, f, pinned_list) for f in listdir(target_dir) if f.endswith('.bz2')]
        for retention in [SlotOfRetention(*slot) for slot in self.plan]:
            retention.muster(files)
        files.sort(key=lambda f: -f.timestamp)
        for file in files:
            if file.pinned:
                log.debug('Keep file ' + str(file))
            else:
                log.info('Delete file ' + str(file))
                if not pretend:
                    unlink(file.filename)


class FileInfo(object):
    def __init__(self, dirpath, filename, pinned_list):
        self.dirpath = dirpath
        self.filename = join(dirpath, filename)
        self.timestamp = getmtime(self.filename)
        self.when = datetime.fromtimestamp(self.timestamp)
        self.pinned = filename in pinned_list

    def __str__(self):
        return ' '.join((self.when.strftime('%Y%m%d%H%M%S'), basename(self.filename)))

    def reduce(self, them):
        if self.pinned != them.pinned:
            return self if self.pinned > them.pinned else them
        else:
            return self if self.timestamp <= them.timestamp else them


class SlotOfRetention:
    def __init__(self, granularity, quantity):
        self.quantity = quantity
        if granularity is None:
            self.granularity = 1
            self._calc = self._calc_secdiv
        elif isinstance(granularity, str):
            self.granularity = granularity
            self._calc = getattr(self, '_calc_' + granularity)
        elif isinstance(granularity, timedelta):
            self.granularity = int(granularity.total_seconds())
            self._calc = self._calc_secdiv
        else:
            raise ValueError('Unknown granularity type %s', type(granularity))

    def muster(self, list_of_files):
        timeslots = {}
        for fileinfo in list_of_files:
            position = self._calc(fileinfo)
            if position not in timeslots:
                timeslots[position] = []
            timeslots[position].append(fileinfo)
        keys = sorted(timeslots.keys(), reverse=True)
        if self.quantity:
            keys = keys[:self.quantity]
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
        try:
            try:
                from . import settings
            except SystemError:
                import settings
        except ImportError:
            settings = None
        dictConfig(getattr(settings, 'LOGGING', {}))
        super().__init__(settings.TARGETS if hasattr(settings, 'TARGETS') else self._targets_from_argv())
        plans = {'': RetentionPlan()}
        for k, v in getattr(settings, 'PLANS', {}).items():
            plans[k] = RetentionPlan(v)
        for item in self:
            key = 'retention_plan'
            plan = item.get(key, '')
            if isinstance(plan, str):
                item[key] = plans[plan]
            elif isinstance(plan, (list, tuple)):
                item[key] = RetentionPlan(plan)
            else:
                raise TypeError(plan)

    def _targets_from_argv(self):
        for item in argv:
            args = item.split(':', 2)
            if len(args) < 2:
                args.append(dirname(args[0]))
            if len(args) < 3:
                args.append('default')
            yield args


def backup_and_retention(target_path=None, backup_dir=None, retention_plan=RetentionPlan(), pin=(), pretend=False):
    if target_path:
        log.info("Backing up: %s to %s", target_path, backup_dir or 'local')
        if not backup_dir:
            backup_dir = dirname(abspath(target_path))
        backup_target_database(target_path, backup_dir)
    elif backup_dir:
        log.info("Applying retention plan to %s", backup_dir)
    else:
        raise ValueError("No target_path or backup_dir in plan; nothing to do!")
    if not isinstance(retention_plan, RetentionPlan):
        retention_plan = RetentionPlan(retention_plan)
    retention_plan.prune(backup_dir, pin, pretend)


if __name__ == '__main__':
    main()
