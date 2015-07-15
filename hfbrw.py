#!/usr/bin/python3
# coding=utf-8
from bz2 import BZ2File
from datetime import datetime
from os.path import dirname, abspath, join
from hashlib import sha512


def do_backup(target_path):
    backup_dir = dirname(abspath(target_path))
    hash_path = join(backup_dir, 'last_hash')
    new_hash = sha512(open(target_path, 'rb').read()).digest()
    if new_hash != open(hash_path, 'rb').read():
        fmt = '%Y%m%d-%H%M.sqlite3.bz2'
        snapshot_path = join(backup_dir, datetime.now().strftime(fmt))
        BZ2File(snapshot_path, 'wb').write(open(target_path, 'rb').read())
        open(hash_path, 'wb').write(new_hash)


if __name__ == '__main__':
    from sys import argv

    for target in argv:
        do_backup(target)
