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
from datetime import datetime
from hashlib import sha512
from logging import getLogger
from os.path import abspath, dirname, join, splitext

from hfbr.retention import RetentionPlan

log = getLogger("hfbr")


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
