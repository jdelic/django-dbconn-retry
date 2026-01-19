Django Database Connection Autoreconnect
========================================

.. image:: https://coveralls.io/repos/github/jdelic/django-dbconn-retry/badge.svg?branch=master
    :target: https://coveralls.io/github/jdelic/django-dbconn-retry?branch=master

.. image:: https://github.com/jdelic/django-dbconn-retry/actions/workflows/django.yml/badge.svg
    :target: https://github.com/jdelic/django-dbconn-retry/actions

This library monkeypatches ``django.db.backends.base.BaseDatabaseWrapper`` so
that when a database operation fails because the underlying TCP connection was
already closed, it first tries to reconnect, instead of immediately raising
an ``OperationException``.


Why is this useful?
-------------------
I use `HAProxy`_ as a load-balancer in front of my PostgreSQL databases all
the time, sometimes in addition to ``pgbouncer``. Even though you can mostly
prevent surprises by enabling TCP keep-alive packets through `tcpka`_,
`clitcpka`_ and `srvtcpka`_, I still encounter situations where the
underlying TCP connection has been closed through the load-balancer. Most often
this results in

.. code-block::

    django.db.utils.OperationalError: server closed the connection unexpectedly
    This probably means the server terminated abnormally before or while
    processing the request.

This library patches Django such that it will try to reconnect once before
failing.

Another application of this is when using `Hashicorp Vault`_, where
credentials for a database connection can expire at any time and then need to
be refreshed from Vault.


How to install?
---------------
Just pull the library in using ``pip install django-dbconn-retry``. Then add
``django_dbconn_retry`` to ``INSTALLED_APPS`` in your ``settings.py``.


Signals
-------
The library provides an interface for other code to plug into the process to,
for example, allow `12factor-vault`_ to refresh the database credentials
before the code tries to reestablish the database connection. These are
implemented using `Django Signals`_.

===========================  ==================================================
Signal                       Description
===========================  ==================================================
``pre_reconnect``            Installs a hook of the type
                             ``Callable[[type, BaseDatabaseWrapper], None]``
                             that will be called before the library tries to
                             reestablish a connection. 12factor-vault uses this
                             to refresh the database credentials from Vault.
``post_reconnect``           Installs a hook of the type
                             ``Callable[[type, BaseDatabaseWrapper], None]``
                             that will be called after the library tried to
                             reestablish the connection. Success or failure has
                             not been tested at this point. So the connection
                             may be in any state.
===========================  ==================================================

Both signals send a parameter ``dbwrapper`` which points to the current instance
of ``django.db.backends.base.BaseDatabaseWrapper`` which allows the signal
receiver to act on the database connection.


Settings
--------
Here’s a list of settings available in django-dbconn-retry and their default values.
You can change the value in your ``settings.py``.

===========================  ==================================================
Setting                       Description
===========================  ==================================================
``MAX_DBCONN_RETRY_TIMES``   Default: ``1``
                             The max times which django-dbconn-retry will try.
``DBCONN_RETRY_DELAY``       Default: ``0``
                             The base delay in seconds before each retry
                             attempt. Used as the initial delay and, together
                             with ``DBCONN_RETRY_BACKOFF``, controls the delay
                             for subsequent retries. Set to ``0`` to retry
                             immediately.
``DBCONN_RETRY_BACKOFF``     Default: ``1``
                             The multiplier applied to the delay after each
                             retry. For example, with ``DBCONN_RETRY_DELAY=1``
                             and ``DBCONN_RETRY_BACKOFF=2``, the delays will
                             be 1s, 2s, 4s, etc. Note that delays grow
                             exponentially and can become very large for
                             higher values. For example, with
                             ``DBCONN_RETRY_DELAY=10``,
                             ``DBCONN_RETRY_BACKOFF=3`` and
                             ``MAX_DBCONN_RETRY_TIMES=10``, the final retry
                             would wait on the order of tens of hours.
                             Choose these settings carefully if very long waits
                             are not acceptable for your deployment.
===========================  ==================================================


License
=======

Copyright (c) 2018, Jonas Maurus
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


.. _12factor-vault: https://github.com/jdelic/12factor-vault/
.. _Django Signals: https://docs.djangoproject.com/en/dev/topics/signals/
.. _HAProxy: http://www.haproxy.org/
.. _tcpka:
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#option%20tcpka
.. _clitcpka:
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#4-option%20clitcpka
.. _srvtcpka:
   https://cbonte.github.io/haproxy-dconv/1.8/configuration.html#option%20srvtcpka
.. _Hashicorp Vault: https://vaultproject.io/
