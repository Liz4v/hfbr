#!/usr/bin/python3
# coding=utf-8
from bz2 import BZ2File
from datetime import datetime
from os.path import abspath, dirname, join, sep
from hashlib import sha512
from sys import argv


def main(cli_args):
    for target in cli_args:
        backup_target_database(target)


def backup_target_database(target_path, backup_dir=None):
    if not backup_dir:
        backup_dir = dirname(abspath(target_path))
    hash_path = join(backup_dir, 'last_hash')
    with open(target_path, 'rb') as target:
        new_hash = sha512(target.read()).digest()
    with open(hash_path, 'rb') as hashfile:
        old_hash = hashfile.read()
    if new_hash != old_hash:
        snapshot_filename = datetime.now().strftime('%Y%m%d-%H%M') + grab_extension(target_path) + '.bz2'
        snapshot_path = join(backup_dir, snapshot_filename)
        with open(target_path, 'rb') as target, BZ2File(snapshot_path, 'wb') as snapshot:
            snapshot.write(target.read())
        with open(hash_path, 'wb') as hashfile:
            hashfile.write(new_hash)


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
    main(argv)
