
.. _Additional Tips:

Additional Tips
---------------

Here are some additional tips as far as administration of a CubicWeb is concerned.

Backup, backup, backup
``````````````````````

It is always a good idea to backup. If your system does not do that,
you should set it up. Note that whenever you do an upgrade,
`cubicweb-ctl` offers you to backup your database.

There are a number of ways for doing backups. Before you go ahead,
make sure the following permissions are correct ::

   # chgrp postgres /var/lib/cubicweb/backup

   # chmod g+ws /var/lib/cubicweb/backup

   # chgrp postgres /etc/cubicweb.d/*<instance>*/sources

   # chmod g+r /etc/cubicweb.d/*<instance>*/sources

**Classic way**

Simply use the pg_dump in a cron ::

    pg_dump -Fc --username=cubicweb --no-owner --file=/var/lib/cubicweb/backup/<instance>-$(date '+%Y-%m-%d_%H:%M:%S').dump

**CubicWeb way**

The CubicWeb way is to use the `db-dump` command. For that, you have to put your passwords in a user-only-readable file at the
root of the postgres user. The file is `.pgpass` (`chmod 0600`), in this case for a socket run connection to postgres ::

    /var/run/postgresql:5432:<instance>:cubicweb:<password>

The postgres documentation for the `.pgpass` format can be found `here`_

Then add the following command to the crontab of the postgres user (`su posgres 'crontab -e'`)::

    # m h  dom mon dow   command
    0 2 * * * cubicweb-ctl db-dump <instance>

**The automated sysadmin way**

You can use a combination `backup-ninja`_ (which has a postgres script in the example directory), `backuppc`)_ (for versionning).

Please note that in the *CubicWeb way* it adds a second location for your password which is error-prone.

.. _`here` : http://www.postgresql.org/docs/current/static/libpq-pgpass.html
.. _`backup-ninja` : https://labs.riseup.net/code/projects/show/backupninja/
.. _`backuppc` : http://backuppc.sourceforge.net/
