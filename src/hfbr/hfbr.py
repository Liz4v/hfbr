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
from logging import getLogger
from logging.config import dictConfig
from os.path import isfile
from sys import argv

from yaml import safe_load

from hfbr.backup import backup_and_retention
from hfbr.retention import RetentionPlan, parse_duration

log = getLogger("hfbr")


def main():
    settings = Settings()
    log.info("^" * 40)
    for item in settings:
        backup_and_retention(**item)
    log.info("v" * 40)


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


if __name__ == "__main__":
    main()
