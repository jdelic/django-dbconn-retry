Django Database Connection Autoreconnect
========================================

This library monkeypatches ``django.db.backends.base.BaseDatabaseWrapper`` so
that when a database operation fails because the underlying TCP connection was
already closed, it first tried to reconnect, instead of immediately raising
an ``OperationException``.


Why is this useful?
-------------------
I use `HAProxy`_ as a load-balancer in front of my PostgreSQL databases all
the time, sometimes in addition to ``pgbouncer``. Even though you can mostly
prevent surprises by enabling TCP keep-alive packets through ``tcpka``_,
``clitcpka``_ and ``srvtcpka``_, I still encounter situations where the
underlying TCP connection has been closed through the load-balancer. Most often
this results in

    django.db.utils.OperationalError: server closed the connection unexpectedly
    This probably means the server terminated abnormally before or while
    processing the request.

This library patches Django such that it try to reconnect once before failing.

Another application of this is when using `Hashicorp Vault`_, where
credentials for a database connection can expire at any time and then need to
be refreshed from Vault.


How to install?
---------------
Just pull the library in using ``pip install django-dbconn-retry``. Then add
``django_dbconn_retry`` to ``INSTALLED_APPS`` in your ``settings.py``.


Provided hooks
--------------
The library provides an interface for other code to plug into the process to,
for example, allow ``12factor-vault``__ to refresh the database credentials
before the code tries to reestablish the database connection.

===========================  ==================================================
Hook                         Description
===========================  ==================================================
``add_pre_reconnect_hook``   Installs a hook of the type 
                             ``Callable[[BaseDatabaseWrapper], None]`` that
                             will be called before the library tries to
                             reestablish a connection. 12factor-vault uses this
                             to refresh the database credentials from Vault.
``add_post_reconnect_hook``  Installs a hook of the type
                             ``Callable[[BaseDatabaseWrapper], None]`` that
                             will be called after the library tried to
                             reestablish the connection. Success or failure has
                             not been tested at this point. So the connection
                             may be in any state.
===========================  ==================================================



.. _HAProxy: http://www.haproxy.org/
.. _tcpka:
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#option%20tcpka
.. _clitcpka: 
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#4-option%20clitcpka
.. _srvtcpka:
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#option%20srvtcpka
.. _Hashicorp Vault: https://vaultproject.io/
