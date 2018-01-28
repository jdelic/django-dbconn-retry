# -* encoding: utf-8 *-
import logging
from unittest.mock import Mock

import sys

from typing import Any

from django.db.backends.base.base import BaseDatabaseWrapper

import django_dbconn_retry as ddr

from django.db import connection, OperationalError
from django.test import TestCase


logging.basicConfig(stream=sys.stderr)
logging.getLogger("django_dbconn_retry").setLevel(logging.DEBUG)
_log = logging.getLogger(__name__)


def raise_operror(*args: Any, **kwargs: Any) -> None:
    raise OperationalError()


class FullErrorTests(TestCase):
    """
    This is SUPERHACKY. I couldn't find a better way to ensure that the
    database connections reliably fail. If I had been able to think of
    a better way, I'd have used it.
    """
    def test_getting_root(self) -> None:
        self.client.get('/')

    def setUp(self) -> None:
        _log.debug("[FullErrorTests] patching for setup")
        self.s_connect = BaseDatabaseWrapper.connect
        BaseDatabaseWrapper.connect = raise_operror
        BaseDatabaseWrapper.connection = property(lambda x: None, lambda x, y: None)  # type: ignore

    def tearDown(self) -> None:
        _log.debug("[FullErrorTests] restoring")
        BaseDatabaseWrapper.connect = self.s_connect
        del BaseDatabaseWrapper.connection

    @classmethod
    def tearDownClass(cls) -> None:
        # this prevents the database rollback from Django, which we don't need in these tests
        # but whenever we do... it'll be hard to work around it, because they fail after
        # BaseDatabaseWrapper has been patched in setUp
        pass

    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.pre_reconnect.connect(cb)
        self.assertRaises(OperationalError, connection.ensure_connection)
        self.assertTrue(cb.called)
        del connection._connection_retries

    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.post_reconnect.connect(cb)
        self.assertRaises(OperationalError, connection.ensure_connection)
        self.assertTrue(cb.called)
        del connection._connection_retries


class ReconnectTests(TestCase):
    def test_getting_root(self) -> None:
        self.client.get('/')

    def setUp(self) -> None:
        from django.db import connection
        _log.debug("[ReconnectTests] closing connection for reconnect test")
        connection.close()

    def test_ensure_closed(self) -> None:
        from django.db import connection
        self.assertTrue(connection.closed)  # should be true after setUp

    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.pre_reconnect.connect(cb)
        self.assertTrue(cb.called)
        from django.db import connection
        self.assertTrue(connection.is_usable())

    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.post_reconnect.connect(cb)
        self.assertTrue(cb.called)
        from django.db import connection
        self.assertTrue(connection.is_usable())
