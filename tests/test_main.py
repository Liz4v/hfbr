import pytest
import yaml

from hfbr.main import Settings, main
from hfbr.retention import RetentionPlan

# ── Settings ────────────────────────────────────────────────────────────────


class TestSettings:
    def test_from_yaml_with_targets(self, tmp_path):
        config = {
            "targets": [
                {"target_path": "/some/path", "backup_dir": "/some/backup"},
            ],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))

        settings = Settings(["-c", str(config_file)])
        assert len(settings) == 1
        assert settings[0]["target_path"] == "/some/path"

    def test_from_yaml_with_named_plans(self, tmp_path):
        config = {
            "plans": {
                "daily": [["1 day", 7]],
            },
            "targets": [
                {"target_path": "/some/path", "retention_plan": "daily"},
            ],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))

        settings = Settings(["-c", str(config_file)])
        assert isinstance(settings[0]["retention_plan"], RetentionPlan)

    def test_from_yaml_with_inline_plan(self, tmp_path):
        config = {
            "targets": [
                {"target_path": "/some/path", "retention_plan": [["1 week", 4]]},
            ],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))

        settings = Settings(["-c", str(config_file)])
        assert isinstance(settings[0]["retention_plan"], RetentionPlan)

    def test_from_yaml_with_logging(self, tmp_path):
        config = {
            "logging": {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "console": {"class": "logging.StreamHandler", "level": "DEBUG"},
                },
                "root": {"level": "DEBUG", "handlers": ["console"]},
            },
            "targets": [{"target_path": "/some/path"}],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))

        settings = Settings(["-c", str(config_file)])
        assert len(settings) == 1

    def test_from_args_with_target_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings = Settings(["/some/target"])
        assert len(settings) == 1
        assert settings[0]["target_path"] == "/some/target"

    def test_from_args_with_target_and_backup(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        settings = Settings(["/some/target", "/some/backup"])
        assert len(settings) == 1
        assert settings[0]["target_path"] == "/some/target"
        assert settings[0]["backup_dir"] == "/some/backup"

    def test_no_args_exits(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        with pytest.raises(SystemExit):
            Settings([])

    def test_empty_yaml_falls_to_args(self, tmp_path):
        config_file = tmp_path / "settings.yaml"
        config_file.write_text("")

        settings = Settings(["-c", str(config_file), "/fallback"])
        assert settings[0]["target_path"] == "/fallback"

    def test_no_retention_plan_in_target(self, tmp_path):
        config = {
            "targets": [{"target_path": "/some/path"}],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))

        settings = Settings(["-c", str(config_file)])
        assert "retention_plan" not in settings[0]

    def test_default_config_in_cwd(self, tmp_path, monkeypatch):
        config = {
            "targets": [{"target_path": "/some/path"}],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))
        monkeypatch.chdir(tmp_path)

        settings = Settings([])
        assert len(settings) == 1
        assert settings[0]["target_path"] == "/some/path"


# ── main ────────────────────────────────────────────────────────────────────


class TestMain:
    def test_main_iterates_settings(self, tmp_path, monkeypatch):
        target = tmp_path / "data.db"
        target.write_bytes(b"content")
        config = {
            "targets": [
                {"target_path": str(target)},
            ],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))
        monkeypatch.chdir(tmp_path)

        main()
        # Verify backup was created
        assert (tmp_path / "last_hash").exists()

    def test_main_multiple_targets(self, tmp_path, monkeypatch):
        t1 = tmp_path / "a.db"
        t2 = tmp_path / "b.db"
        t1.write_bytes(b"aaa")
        t2.write_bytes(b"bbb")
        backup1 = tmp_path / "backup1"
        backup2 = tmp_path / "backup2"
        backup1.mkdir()
        backup2.mkdir()

        config = {
            "targets": [
                {"target_path": str(t1), "backup_dir": str(backup1)},
                {"target_path": str(t2), "backup_dir": str(backup2)},
            ],
        }
        config_file = tmp_path / "settings.yaml"
        config_file.write_text(yaml.dump(config))
        monkeypatch.chdir(tmp_path)

        main()
        assert (backup1 / "last_hash").exists()
        assert (backup2 / "last_hash").exists()
