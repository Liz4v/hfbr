#!/usr/bin/python3
# coding=utf-8
from bz2 import BZ2File
from datetime import datetime
from os import listdir
from os.path import abspath, dirname, getmtime, join, sep
from hashlib import sha512
from sys import argv


def main(cli_args):
    for target in cli_args:
        backup_target_database(*target.split('=', 1))


def backup_target_database(target_path, backup_dir=None):
    if not backup_dir:
        backup_dir = dirname(abspath(target_path))
    hash_path = join(backup_dir, 'last_hash')
    hasher = sha512()
    with open(target_path, 'rb') as target:
        block_transfer(target.read, hasher.update)
    with open(hash_path, 'rb') as hashfile:
        old_hash = hashfile.read()
    if hasher.digest() != old_hash:
        snapshot_filename = datetime.now().strftime('%Y%m%d-%H%M') + grab_extension(target_path) + '.bz2'
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


def grab_extension(filename_or_path):
    try:
        filename = filename_or_path[filename_or_path.rindex(sep) + len(sep):]
    except ValueError:
        filename = filename_or_path
    try:
        return filename[filename.rindex('.'):]
    except ValueError:
        return ''


class RetentionPlan:
    def __init__(self, plan_description=((None, None),)):
        transposed_plan = [tuple(x) for x in zip(*plan_description)]
        self.granularity, self.retention = transposed_plan

    def prune(self, target_dir='.', pinned_list=()):
        files = [FileInfo(target_dir, f, pinned_list, self)
                 for f in listdir(target_dir) if f.endswith('.bz2')]
        files.sort(key=lambda i: -i.timestamp)  # Most recent to oldest.


class FileInfo(object):
    def __init__(self, dirpath, filename, pinned_list, plan):
        self.dirpath = dirpath
        self.filename = join(dirpath, filename)
        self.timestamp = getmtime(self.filename)
        self.when = datetime.fromtimestamp(self.timestamp)
        self.pinned = filename in pinned_list

    def __str__(self):
        return '<%s %s %s>' % ('##' if self.pinned else '--', self.when.strftime('%Y%m%d%H%M%S'), self.filename)


if __name__ == '__main__':
    main(argv)
