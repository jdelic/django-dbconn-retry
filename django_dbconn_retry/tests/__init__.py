# -* encoding: utf-8 *-
from unittest.mock import Mock

import django_dbconn_retry as ddr

from django.test import TestCase


class ReconnectTests(TestCase):
    def test_getting_root(self):
        self.client.get('/')

    def test_prehook(self):
        cb = Mock()
        ddr.add_pre_reconnect_hook(cb)
        cb.assert_called()

    def test_posthook(self):
        cb = Mock()
        ddr.add_post_reconnect_hook(cb)
        cb.assert_called()
