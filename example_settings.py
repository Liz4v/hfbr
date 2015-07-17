# -*- coding: utf-8 -*-
from datetime import timedelta
from sys import stdout

TARGETS = [
    {
        'target_path': 'db.sqlite',
        'backup_dir': '/var/backup/sqlite-db',
        'retention_plan': 'default',
        'pin': ('20150717-1155.sq3.bz2',),
        'prune': False,
    },
]

PLANS = {
    'default': (
        # Snapshots are pinned in the order these rules are declared.
        ('year', None),  # permanent yearly snapshots
        ('month', 9),  # 9 monthly snapshots
        (timedelta(weeks=1), 6),  # 6 weekly snapshots
        (timedelta(days=1), 5),  # 5 daily snapshots
        (timedelta(hours=1), 18),  # 18 hourly snapshots
        (None, 10),  # 10 latest snapshots
    )
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'fmt': {'datefmt': '%Y-%m-%d %H:%M:%S',
                           'format': '%(asctime)s %(levelname)-8s %(name)-15s %(message)s'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'fmt', 'stream': stdout},
        'file': {'class': 'logging.handlers.RotatingFileHandler',
                 'formatter': 'fmt',
                 'filename': '/tmp/hfbrw.log',
                 'maxBytes': 4 * 1024 * 1024,  # 4 MB
                 'backupCount': 5},
    },
    'loggers': {'hfbrw': {'handlers': ['console'], 'level': 'INFO'}},
}
