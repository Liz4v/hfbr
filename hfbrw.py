#!/usr/bin/python3
# coding=utf-8
from bz2 import BZ2File
from datetime import datetime
from os.path import abspath, dirname, join, sep
from hashlib import sha512


def do_backup(target_path, backup_dir=None):
    if not backup_dir:
        backup_dir = dirname(abspath(target_path))
    hash_path = join(backup_dir, 'last_hash')
    new_hash = sha512(open(target_path, 'rb').read()).digest()
    if new_hash != open(hash_path, 'rb').read():
        snapshot_filename = datetime.now().strftime('%Y%m%d-%H%M') + grab_extension(target_path) + '.bz2'
        snapshot_path = join(backup_dir, snapshot_filename)
        BZ2File(snapshot_path, 'wb').write(open(target_path, 'rb').read())
        open(hash_path, 'wb').write(new_hash)


def grab_extension(filename_or_path):
    try:
        filename = filename_or_path[filename_or_path.rindex(sep) + len(sep):]
    except ValueError:
        filename = filename_or_path
    try:
        return filename[filename.rindex('.'):]
    except ValueError:
        return ''


if __name__ == '__main__':
    from sys import argv

    for target in argv:
        do_backup(target)
