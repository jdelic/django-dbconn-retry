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


class ReconnectTests(TestCase):
    """
    This is SUPERHACKY. I couldn't find a better way to ensure that the
    database connections reliably fail. If I had been able to think of
    a better way, I'd have used it.
    """
    def test_getting_root(self) -> None:
        self.client.get('/')

    def setUp(self):
        _log.debug("patching for setup")
        self.s_connect = BaseDatabaseWrapper.connect
        BaseDatabaseWrapper.connect = raise_operror
        BaseDatabaseWrapper.connection = property(lambda x: None, lambda x: None)

    def tearDown(self):
        _log.debug("restoring")
        BaseDatabaseWrapper.connect = self.s_connect
        del BaseDatabaseWrapper.connection

    @classmethod
    def tearDownClass(cls):
        pass

    def test_prehook(self) -> None:
        cb = Mock(name='pre_reconnect_hook')
        ddr.add_pre_reconnect_hook(cb)
        self.assertRaises(OperationalError, connection.ensure_connection)
        cb.assert_called()
        del connection._connection_retries

    def test_posthook(self) -> None:
        cb = Mock(name='post_reconnect_hook')
        ddr.add_post_reconnect_hook(cb)
        self.assertRaises(OperationalError, connection.ensure_connection)
        cb.assert_called()
        del connection._connection_retries
