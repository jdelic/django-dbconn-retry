# -* encoding: utf-8 *-
import logging

from django.apps.config import AppConfig
from django.db import utils as django_db_utils
from django.db.backends.base import base as django_db_base

from typing import Union, Tuple, Callable, List

_log = logging.getLogger(__name__)
default_app_config = 'django_dbconn_retry.DjangoIntegration'

pre_reconnect_hooks = []  # type: List[Callable[[django_db_base.BaseDatabaseWrapper], None]]
post_reconnect_hooks = []  # type: List[Callable[[django_db_base.BaseDatabaseWrapper], None]]


_operror_types = ()  # type: Union[Tuple[type], Tuple]
_operror_types += (django_db_utils.OperationalError,)
try:
    import psycopg2
except ImportError:
    pass
else:
    _operror_types += (psycopg2.OperationalError,)

try:
    import sqlite3
except ImportError:
    pass
else:
    _operror_types += (sqlite3.OperationalError,)

try:
    import MySQLdb
except ImportError:
    pass
else:
    _operror_types += (MySQLdb.OperationalError,)


def add_pre_reconnect_hook(hook: Callable[[django_db_base.BaseDatabaseWrapper], None]) -> None:
    global pre_reconnect_hooks
    pre_reconnect_hooks.append(hook)


def add_post_reconnect_hook(hook: Callable[[django_db_base.BaseDatabaseWrapper], None]) -> None:
    global post_reconnect_hooks
    post_reconnect_hooks.append(hook)


def monkeypatch_django() -> None:
    global pre_reconnect_hooks, post_reconnect_hooks

    def ensure_connection_with_retries(self: django_db_base.BaseDatabaseWrapper) -> None:
        if self.connection is not None and self.connection.closed:
            _log.debug("failed connection detected")
            self.connection = None

        if self.connection is None:
            with self.wrap_database_errors:
                try:
                    self.connect()
                except Exception as e:
                    if isinstance(e, _operror_types):
                        if hasattr(self, "_connection_retries") and self._connection_retries >= 1:
                            _log.error("Reconnecting to the database didn't help %s", str(e))
                            raise
                        else:
                            _log.info("Database connection failed. Refreshing...")
                            self._connection_retries = 1

                            for hook in pre_reconnect_hooks:
                                hook(self)

                            self.ensure_connection()

                            for hook in post_reconnect_hooks:
                                hook(self)
                    else:
                        _log.debug("Database connection failed, but not due to a known error for vault12factor %s",
                                   str(e))
                        raise
                else:
                    self._connection_retries = 0

    _log.debug("12factor-vault: monkeypatching BaseDatabaseWrapper")
    django_db_base.BaseDatabaseWrapper.ensure_connection = ensure_connection_with_retries


class DjangoIntegration(AppConfig):
    name = "django_dbconn_retry"

    def ready(self) -> None:
        monkeypatch_django()


