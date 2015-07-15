#!/usr/bin/python3
# coding=utf-8
from bz2 import BZ2File
from datetime import datetime
from os.path import dirname, abspath, join
from hashlib import sha512


def do_backup(target):
    backup_dir = dirname(abspath(target))
    hash_file = join(backup_dir, 'last_hash')
    new_hash = sha512(open(target, 'rb').read()).digest()
    if new_hash != open(hash_file, 'rb').read():
        fmt = '%Y%m%d-%H%M.sqlite3.bz2'
        snapshot_file = join(backup_dir, datetime.now().strftime(fmt))
        BZ2File(snapshot_file, 'wb').write(open(target, 'rb').read())
        open(hash_file, 'wb').write(new_hash)


if __name__ == '__main__':
    from sys import argv

    for target in argv:
        do_backup(target)
