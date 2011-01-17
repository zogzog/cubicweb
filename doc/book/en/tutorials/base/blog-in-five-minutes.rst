.. -*- coding: utf-8 -*-

.. _TutosBaseBlogFiveMinutes:

Get a blog running in five minutes!
-----------------------------------

For Debian or Ubuntu users, first install the following packages
(:ref:`DebianInstallation`)::

    cubicweb, cubicweb-dev, cubicweb-blog

For Windows or Mac OS X users, you must install |cubicweb| from source (see
:ref:`SourceInstallation` and :ref:`WindowsInstallation`).

Then create and initialize your instance::

    cubicweb-ctl create blog myblog

You'll be asked a few questions, and you can keep the default answer for most of
them. The one question you'll have to think about is the database you'll want to
use for that instance. For a quick test, if you don't have `postgresql` installed
and configured (see :ref:`PostgresqlConfiguration`), it's higly recommended to
choose `sqlite` when asked for which database driber to use, since it has a much
simple setup (no database server needed).

One the process is completed (including database initialisation), you can start
your instance by using: ::

    cubicweb-ctl start -D myblog

The `-D` option activate the debugging mode, removing it will launch the instance
as a daemon in the background.


About file-system permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unless you installed from sources, above commands assumes that you have root
access to the :file:`/etc/` path. In order to initialize your instance as a
regulary user, within your home directory, you can use the :envvar:`CW_MODE`
environment variable: ::

  export CW_MODE=user

then create a :file:`~/etc/cubicweb.d` directory that will hold your instances.

More information about how to configure your own environment in :ref:`ResourceMode`.


Instance parameters
~~~~~~~~~~~~~~~~~~~

If you would like to change database parameters such as the database host or the
user name used to connect to the database, edit the `sources` file located in the
:file:`/etc/cubicweb.d/myblog` directory.

Then relaunch the database creation::

     cubicweb-ctl db-create myblog

Other paramaters, like web server or emails parameters, can be modified in the
:file:`/etc/cubicweb.d/myblog/all-in-one.conf` file.

You'll have to restart the instance after modification in one of those files.

This is it. Your blog is functionnal and running. Visit http://localhost:8080 and enjoy it!

