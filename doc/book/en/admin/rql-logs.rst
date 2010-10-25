.. -*- coding: utf-8 -*-

RQL logs
========

You can configure the *CubicWeb* instance to keep a log
of the queries executed against your database. To do so,
edit the configuration file of your instance
``.../etc/cubicweb.d/myapp/all-in-one.conf`` and uncomment the
variable ``query-log-file``::

  # web instance query log file
  query-log-file=/tmp/rql-myapp.log

