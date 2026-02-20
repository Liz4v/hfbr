# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**hfbr** (High Frequency Backup and Retention) is a Python CLI tool that backs up small files on a frequent schedule, avoids duplicates via SHA-512 hashing, and prunes old snapshots using configurable retention plans. Designed to run from cron.

## Build & Development

- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **Python**: >=3.14
- **Install dependencies**: `uv sync`
- **Run the tool**: `uv run hfbr` (reads `settings.yaml` in cwd) or `uv run hfbr <target_path> [backup_dir]` (CLI mode)
- **Test**: `uv run pytest` (includes coverage report and `ty check` type checking)
- **Lint**: `uv run ruff check` (line-length: 120)
- **Format**: `uv run ruff format`
- **Type check**: `uv run ty check`

## Architecture

The package is split into three modules under [src/hfbr/](src/hfbr/). Entry point is `main()` in `hfbr.py`.

**Flow**: `main()` → `Settings()` loads `settings.yaml` (or parses argv) → iterates targets → `backup_and_retention()` per target.

**Modules**:

- [src/hfbr/hfbr.py](src/hfbr/hfbr.py) — `Settings` (parses `settings.yaml` or CLI argv, resolves named retention plans) and `main()` entry point.
- [src/hfbr/backup.py](src/hfbr/backup.py) — `backup_target_database()` (SHA-512 change detection, bz2-compressed snapshots), `block_transfer()`, and `backup_and_retention()` per-target orchestrator.
- [src/hfbr/retention.py](src/hfbr/retention.py) — `RetentionPlan`, `SlotOfRetention`, `FileInfo`, and `parse_duration()`. Each slot has a granularity (`year`, `month`, timedelta, or `null`) and a quantity. Slots group files into time buckets and pin the earliest file per bucket up to the quantity limit.

**Config structure** (`settings.yaml`): three top-level keys — `targets` (list of backup jobs), `plans` (named retention plan definitions), `logging` (Python dictConfig).
