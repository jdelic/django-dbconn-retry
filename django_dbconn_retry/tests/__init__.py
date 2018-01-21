# -* encoding: utf-8 *-
from unittest.mock import Mock

import django_dbconn_retry as ddr

from django.db import connection, OperationalError
from django.test import TestCase


class ReconnectTests(TestCase):
    def test_getting_root(self) -> None:
        self.client.get('/')

    def test_prehook(self) -> None:
        cb = Mock()
        ddr.add_pre_reconnect_hook(cb)
        connection.closed = property(lambda: True, lambda: None)
        self.assertRaises(OperationalError, self.client.get('/'))
        cb.assert_called()

    def test_posthook(self) -> None:
        cb = Mock()
        ddr.add_post_reconnect_hook(cb)
        connection.closed = property(lambda: True, lambda: None)
        self.assertRaises(OperationalError, self.client.get('/'))
        cb.assert_called()

