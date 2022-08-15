# -* encoding: utf-8 *-
import django


from django_dbconn_retry.apps import pre_reconnect, post_reconnect, monkeypatch_django, DjangoIntegration


__all__ = [pre_reconnect, post_reconnect, monkeypatch_django, DjangoIntegration]

if django.VERSION < (3, 2):
    default_app_config = 'django_dbconn_retry.DjangoIntegration'
