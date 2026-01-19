# -* encoding: utf-8 *-
import random
import sys
import logging

from unittest.mock import Mock

from typing import Any

import django_dbconn_retry as ddr

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db import connection, OperationalError, ProgrammingError, transaction
from django.test import TestCase, TransactionTestCase, override_settings


logging.basicConfig(stream=sys.stderr)
logging.getLogger("django_dbconn_retry").setLevel(logging.DEBUG)
_log = logging.getLogger(__name__)


class FullErrorTests(TestCase):
    """
    This is SUPERHACKY. I couldn't find a better way to ensure that the
    database connections reliably fail. If I had been able to think of
    a better way, I'd have used it.
    """
    max_dbconn_retry_times = random.randint(1, 100)

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

    def do_assert(self, cb):
        self.assertRaises(OperationalError, connection.ensure_connection)
        self.assertTrue(cb.called)
        self.assertEqual(connection._connection_retries, self.max_dbconn_retry_times)
        del connection._connection_retries

    @override_settings(MAX_DBCONN_RETRY_TIMES=max_dbconn_retry_times)
    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.pre_reconnect.connect(cb)
        self.do_assert(cb)

    @override_settings(MAX_DBCONN_RETRY_TIMES=max_dbconn_retry_times)
    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.post_reconnect.connect(cb)
        self.do_assert(cb)


def fix_connection(sender: type, *, dbwrapper: BaseDatabaseWrapper, **kwargs: Any) -> None:
    dbwrapper.connect = dbwrapper.s_connect


class ReconnectTests(TransactionTestCase):

    def test_ensure_closed(self) -> None:
        from django.db import connection
        connection.close()
        self.assertFalse(connection.is_usable())  # should be true after setUp

    def do_assert(self, cb):
        from django.db import connection
        connection.close()
        connection.s_connect = connection.connect
        connection.connect = Mock(side_effect=OperationalError('reconnect testing'))
        connection.ensure_connection()
        self.assertTrue(cb.called)
        self.assertTrue(connection.is_usable())
        self.assertEqual(connection._connection_retries, 0)

    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.pre_reconnect.connect(fix_connection)
        ddr.pre_reconnect.connect(cb)
        self.do_assert(cb)

    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.pre_reconnect.connect(fix_connection)
        ddr.post_reconnect.connect(cb)
        self.do_assert(cb)


class AtomicBlockTests(TransactionTestCase):

    def test_no_retry_when_connection_lost_in_atomic_block(self) -> None:
        from django.db import connection

        connection.ensure_connection()

        with transaction.atomic():
            mock_conn = Mock()
            mock_conn.closed = True
            connection.connection = mock_conn

            with self.assertRaises(ProgrammingError):
                connection.ensure_connection()

    def test_lazy_connection_in_atomic_block_allowed(self) -> None:
        from django.db import connection

        connection.close()

        with transaction.atomic():
            connection.ensure_connection()
            self.assertTrue(connection.is_usable())
