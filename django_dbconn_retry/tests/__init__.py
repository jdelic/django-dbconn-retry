# -* encoding: utf-8 *-

from django.test import TestCase


class ReconnectTests(TestCase):
    def test_getting_root(self):
        self.client.get('/')
