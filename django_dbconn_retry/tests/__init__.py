# -* encoding: utf-8 *-
import random
import sys
import logging

from unittest.mock import Mock, patch

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

    @override_settings(MAX_DBCONN_RETRY_TIMES=max_dbconn_retry_times)
    def test_non_operational_error_propagates(self) -> None:
        BaseDatabaseWrapper.connect = Mock(side_effect=ValueError('not a db error'))
        self.assertRaises(ValueError, connection.ensure_connection)
        BaseDatabaseWrapper.connect.assert_called_once()


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

    @override_settings(MAX_DBCONN_RETRY_TIMES=3)
    @patch('django_dbconn_retry.apps.time.sleep')
    def test_no_delay_by_default(self, mock_sleep: Mock) -> None:
        """Test that sleep is not called with default settings (delay=0)."""
        self.assertRaises(OperationalError, connection.ensure_connection)
        mock_sleep.assert_not_called()
        self.assertEqual(connection._connection_retries, 3)
        del connection._connection_retries

    @override_settings(MAX_DBCONN_RETRY_TIMES=3, DBCONN_RETRY_DELAY=1.0)
    @patch('django_dbconn_retry.apps.time.sleep')
    def test_constant_delay_by_default(self, mock_sleep: Mock) -> None:
        """Test that delay stays constant with default backoff (backoff=1)."""
        self.assertRaises(OperationalError, connection.ensure_connection)
        # With default backoff=1, all delays should be equal to the base delay
        self.assertEqual(mock_sleep.call_count, 3)
        for call in mock_sleep.call_args_list:
            self.assertEqual(call[0][0], 1.0)
        del connection._connection_retries

    @override_settings(DBCONN_RETRY_DELAY="invalid")
    @patch("django_dbconn_retry.apps.time.sleep")
    def test_invalid_retry_delay(self, mock_sleep: Mock) -> None:
        """Test that an invalid delay defaults to zero"""
        self.assertRaises(OperationalError, connection.ensure_connection)
        mock_sleep.assert_not_called()
        self.assertEqual(connection._connection_retries, 1)
        del connection._connection_retries

    @override_settings(
        MAX_DBCONN_RETRY_TIMES=3,
        DBCONN_RETRY_DELAY=1.0,
        DBCONN_RETRY_BACKOFF="invalid",
    )
    @patch("django_dbconn_retry.apps.time.sleep")
    def test_invalid_retry_backoff(self, mock_sleep: Mock) -> None:
        """Test that an invalid backoff defaults to no backoff"""
        self.assertRaises(OperationalError, connection.ensure_connection)
        self.assertEqual(mock_sleep.call_count, 3)
        for call in mock_sleep.call_args_list:
            self.assertEqual(call[0][0], 1.0)
        del connection._connection_retries


class MaxRetriesTests(TestCase):
    """
    Tests for MAX_DBCONN_RETRY_TIMES validation and the zero-retries case.
    """

    def setUp(self) -> None:
        _log.debug("[MaxRetriesTests] patching for setup")
        self.s_connect = BaseDatabaseWrapper.connect
        BaseDatabaseWrapper.connect = Mock(side_effect=OperationalError('max retries testing'))
        BaseDatabaseWrapper.connection = property(lambda x: None, lambda x, y: None)  # type: ignore

    def tearDown(self) -> None:
        _log.debug("[MaxRetriesTests] restoring")
        BaseDatabaseWrapper.connect = self.s_connect
        del BaseDatabaseWrapper.connection

    @override_settings(MAX_DBCONN_RETRY_TIMES=0)
    def test_zero_disables_retries(self) -> None:
        pre_cb = Mock(name='pre_reconnect_hook')
        post_cb = Mock(name='post_reconnect_hook')
        ddr.pre_reconnect.connect(pre_cb)
        ddr.post_reconnect.connect(post_cb)
        self.assertRaises(OperationalError, connection.ensure_connection)
        BaseDatabaseWrapper.connect.assert_called_once()
        self.assertFalse(pre_cb.called)
        self.assertFalse(post_cb.called)

    @override_settings(MAX_DBCONN_RETRY_TIMES="invalid")
    def test_invalid_max_retry_times(self) -> None:
        self.assertRaises(OperationalError, connection.ensure_connection)
        self.assertEqual(connection._connection_retries, 1)
        del connection._connection_retries


class AtomicBlockTests(TransactionTestCase):
    """
    Tests for connection retry behavior inside transaction.atomic() blocks.
    """

    def test_no_retry_when_connection_lost_in_atomic_block(self) -> None:
        from django.db import connection

        connection.ensure_connection()

        with transaction.atomic():
            mock_conn = Mock()
            mock_conn.closed = True
            connection.connection = mock_conn

            with self.assertRaises(ProgrammingError):
                connection.ensure_connection()

        # After exiting the atomic block, reconnection should work
        connection.ensure_connection()
        self.assertTrue(connection.is_usable())

    def test_no_retry_when_connection_closed_in_atomic_block(self) -> None:
        from django.db import connection

        connection.ensure_connection()

        with transaction.atomic():
            connection.close()

            with self.assertRaises(ProgrammingError):
                connection.ensure_connection()

        # After exiting the atomic block, reconnection should work
        connection.ensure_connection()
        self.assertTrue(connection.is_usable())

    def test_lazy_connection_in_atomic_block_allowed(self) -> None:
        from django.db import connection

        connection.close()

        with transaction.atomic():
            connection.ensure_connection()
            self.assertTrue(connection.is_usable())
