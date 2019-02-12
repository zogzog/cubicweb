.. -*- coding: utf-8 -*-

.. _TutosBaseBlogFiveMinutes:

Get a blog running in five minutes!
-----------------------------------

For Debian or Ubuntu users, first install the following packages
(:ref:`DebianInstallation`)::

    cubicweb, cubicweb-dev, cubicweb-twisted, cubicweb-blog

Windows or Mac OS X users must install |cubicweb| from source (see
:ref:`SourceInstallation` and :ref:`WindowsInstallation`).

You can also install those packages using pip in a virtualenv::

   virtualenv venv
   source venv/bin/activate
   pip install cubicweb[etwist] cubicweb-dev cubicweb-blog

Then create and initialize your instance::

    cubicweb-ctl create blog myblog

The `blog` argument is the cube on which you want to base your instance and
`myblog` is the name of your instance.

.. Note::

   If you get an a permission error of this kind `OSError: [Errno 13]
   Permission denied: '/etc/cubicweb.d/myblog'`, read the :ref:`next section`.

You'll be asked a few questions, and you can keep the default answer for most of
them. The one question you'll have to think about is the database you'll want to
use for that instance. For a quick test, if you don't have `postgresql` installed
and configured (see :ref:`PostgresqlConfiguration`), it's highly recommended to
choose `sqlite` when asked for which database driver to use, since it has a much
simple setup (no database server needed).

One the process is completed (including database initialisation), you can start
your instance by using: ::

    cubicweb-ctl start -D myblog

The `-D` option activates the debugging mode. Removing it will launch the instance
as a daemon in the background, and ``cubicweb-ctl stop myblog`` will stop
it in that case.

.. Note::

   If you get a traceback when going on the web interface make sure your
   version of twisted is **inferior** to 17.

.. _AboutFileSystemPermissions:

About file system permissions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Unless you installed from sources, the above commands assume that you have root
access to the :file:`/etc/` directory. In order to initialize your instance as a
regular user, within your home directory, you can use the :envvar:`CW_MODE`
environment variable: ::

  export CW_MODE=user

then create a :file:`~/etc/cubicweb.d` directory that will hold your instances.

More information about how to configure your own environment is
available in :ref:`ResourceMode`.


Instance parameters
~~~~~~~~~~~~~~~~~~~

If you would like to change database parameters such as the database host or the
user name used to connect to the database, edit the `sources` file located in the
:file:`/etc/cubicweb.d/myblog` directory.

Then relaunch the database creation::

     cubicweb-ctl db-create myblog

Other parameters, like web server or emails parameters, can be modified in the
:file:`/etc/cubicweb.d/myblog/all-in-one.conf` file (or :file:`~/etc/cubicweb.d/myblog/all-in-one.conf` depending on your configuration.)

You'll have to restart the instance after modification in one of those files.

This is it. Your blog is functional and running. Visit http://localhost:8080 and enjoy it!
