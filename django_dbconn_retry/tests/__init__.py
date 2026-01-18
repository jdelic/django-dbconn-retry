# -* encoding: utf-8 *-
import random
import sys
import logging

from unittest.mock import Mock, patch

from typing import Any

import django_dbconn_retry as ddr

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db import connection, OperationalError, transaction
from django.test import TestCase, override_settings


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


class ReconnectTests(TestCase):

    @classmethod
    def tearDownClass(cls) -> None:
        return

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
        ReconnectTests.cls_atomics['default'] = transaction.atomic(using='default')
        ReconnectTests.cls_atomics['default'].__enter__()
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


class DelayBackoffTests(TestCase):
    """
    Tests for the delay and backoff retry functionality.
    """

    def setUp(self) -> None:
        _log.debug("[DelayBackoffTests] patching for setup")
        self.s_connect = BaseDatabaseWrapper.connect
        BaseDatabaseWrapper.connect = Mock(side_effect=OperationalError('backoff testing'))
        BaseDatabaseWrapper.connection = property(lambda x: None, lambda x, y: None)  # type: ignore

    def tearDown(self) -> None:
        _log.debug("[DelayBackoffTests] restoring")
        BaseDatabaseWrapper.connect = self.s_connect
        del BaseDatabaseWrapper.connection

    @override_settings(MAX_DBCONN_RETRY_TIMES=3, DBCONN_RETRY_DELAY=1.0, DBCONN_RETRY_BACKOFF=2.0)
    @patch('django_dbconn_retry.apps.time.sleep')
    def test_delay_with_backoff(self, mock_sleep: Mock) -> None:
        """Test that delay increases with backoff multiplier."""
        self.assertRaises(OperationalError, connection.ensure_connection)
        # With 3 retries, delay=1.0, backoff=2.0:
        # retry 1: 1.0 * 2.0^0 = 1.0
        # retry 2: 1.0 * 2.0^1 = 2.0
        # retry 3: 1.0 * 2.0^2 = 4.0
        self.assertEqual(mock_sleep.call_count, 3)
        expected_delays = [1.0, 2.0, 4.0]
        for i, call in enumerate(mock_sleep.call_args_list):
            self.assertEqual(call[0][0], expected_delays[i])
        del connection._connection_retries
