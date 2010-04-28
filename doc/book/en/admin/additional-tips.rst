
.. _Additional Tips:

Backups (mostly with postgresql)
--------------------------------

It is always a good idea to backup. If your system does not do that,
you should set it up. Note that whenever you do an upgrade,
`cubicweb-ctl` offers you to backup your database.  There are a number
of ways for doing backups.

Using postgresql (and only that)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before you
go ahead, make sure the following permissions are correct ::

   # chgrp postgres /var/lib/cubicweb/backup
   # chmod g+ws /var/lib/cubicweb/backup
   # chgrp postgres /etc/cubicweb.d/*<instance>*/sources
   # chmod g+r /etc/cubicweb.d/*<instance>*/sources

Simply use the pg_dump in a cron installed for `postgres` user on the database server::

    # m h  dom mon dow   command
    0 2 * * * pg_dump -Fc --username=cubicweb --no-owner <instance> > /var/backups/<instance>-$(date '+%Y-%m-%d_%H:%M:%S').dump

Using :command:`cubicweb-ctl db-dump`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The CubicWeb way is to use the :command:`db-dump` command. For that,
you have to put your passwords in a user-only-readable file at the
home directory of root user.  The file is `.pgpass` (`chmod 0600`), in
this case for a socket run connection to PostgreSQL ::

    /var/run/postgresql:5432:<instance>:<database user>:<database password>

The postgres documentation for the `.pgpass` format can be found `here`_

Then add the following command to the crontab of the user (`crontab -e`)::

    # m h  dom mon dow   command
    0 2 * * * cubicweb-ctl db-dump <instance>


Backup ninja
~~~~~~~~~~~~

You can use a combination `backup-ninja`_ (which has a postgres script in the
example directory), `backuppc`)_ (for versionning).

Please note that in the *CubicWeb way* it adds a second location for your
password which is error-prone.

.. _`here` : http://www.postgresql.org/docs/current/static/libpq-pgpass.html
.. _`backup-ninja` : https://labs.riseup.net/code/projects/show/backupninja/
.. _`backuppc` : http://backuppc.sourceforge.net/

.. warning::

  Remember that these indications will fail you whenever you use
  another database backend than postgres. Also it does properly handle
  externally managed data such as files (using the Bytes File System
  Storage).
