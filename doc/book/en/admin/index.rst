.. -*- coding: utf-8 -*-

.. _Part3:

-------------------------
Part III - Administration
-------------------------

This part is for installation and administration of the *CubicWeb* framework and
instances based on that framework.

.. toctree::
   :maxdepth: 1
   :numbered:

   setup
   create-instance
   instance-config
   site-config
   multisources
   ldap
   pyro
   gae
   additional-tips

RQL logs
--------

You can configure the *CubicWeb* instance to keep a log
of the queries executed against your database. To do so,
edit the configuration file of your instance
``.../etc/cubicweb.d/myapp/all-in-one.conf`` and uncomment the
variable ``query-log-file``::

  # web instance query log file
  query-log-file=/tmp/rql-myapp.log

