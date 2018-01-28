# -* encoding: utf-8 *-
import sys
import logging

from unittest.mock import Mock

from typing import Any

import django_dbconn_retry as ddr

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db import connection, OperationalError, transaction
from django.test import TestCase


logging.basicConfig(stream=sys.stderr)
logging.getLogger("django_dbconn_retry").setLevel(logging.DEBUG)
_log = logging.getLogger(__name__)


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
        BaseDatabaseWrapper.connect = Mock(side_effect=OperationalError('fail testing'))
        BaseDatabaseWrapper.connection = property(lambda x: None, lambda x, y: None)  # type: ignore

    def tearDown(self) -> None:
        _log.debug("[FullErrorTests] restoring")
        BaseDatabaseWrapper.connect = self.s_connect
        del BaseDatabaseWrapper.connection

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


def fix_connection(sender: type, *, dbwrapper: BaseDatabaseWrapper, **kwargs: Any) -> None:
    dbwrapper.connect = dbwrapper.s_connect


class ReconnectTests(TestCase):
    @classmethod
    def tearDownClass(cls) -> None:
        return

    def test_ensure_closed(self) -> None:
        from django.db import connection
        connection.close()
        self.assertFalse(connection.is_usable())  # should be true after setUp

    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.pre_reconnect.connect(fix_connection)
        ddr.pre_reconnect.connect(cb)
        from django.db import connection
        connection.close()
        connection.s_connect = connection.connect
        connection.connect = Mock(side_effect=OperationalError('reconnect testing'))
        connection.ensure_connection()
        ReconnectTests.cls_atomics['default'] = transaction.atomic(using='default')
        ReconnectTests.cls_atomics['default'].__enter__()
        self.assertTrue(cb.called)
        self.assertTrue(connection.is_usable())

    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.pre_reconnect.connect(fix_connection)
        ddr.post_reconnect.connect(cb)
        from django.db import connection
        connection.close()
        connection.s_connect = connection.connect
        connection.connect = Mock(side_effect=OperationalError('reconnect testing'))
        connection.ensure_connection()
        ReconnectTests.cls_atomics['default'] = transaction.atomic(using='default')
        ReconnectTests.cls_atomics['default'].__enter__()
        self.assertTrue(cb.called)
        self.assertTrue(connection.is_usable())
