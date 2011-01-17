.. -*- coding: utf-8 -*-

.. _BlogFiveMinutes:

Get a blog running in five minutes!
-----------------------------------

For Debian or Ubuntu users, first install the following packages
(:ref:`DebianInstallation`)::

    cubicweb, cubicweb-dev, cubicweb-blog

For Windows or Mac OS X users, you must install |cubicweb| from source (see
:ref:`SourceInstallation` and :ref:`WindowsInstallation`).

Then create and initialize your instance::

    cubicweb-ctl create blog myblog

And start it::

    cubicweb-ctl start -D myblog

The -D option is the debugging mode of |cubicweb|, removing it will lauch the
instance in the background.

Permission
~~~~~~~~~~

This command assumes that you have root access to the /etc/ path. In order to initialize your instance as a `user` (from scratch), please check your current PYTHONPATH then create the ~/etc/cubicweb.d directory.

Instance parameters
~~~~~~~~~~~~~~~~~~~

If you would like to change some instance parameters, for example, the main
database host or the user name, edit the `sources` file located in the
:file:`/etc/cubicweb.d/myblog` directory.

Then relaunch the database creation::

     cubicweb-ctl db-create myblog

Other paramaters, like web server or emails parameters, can be modified in the
:file:`/etc/cubicweb.d/myblog/all-in-one.conf` file.

This is it. Your blog is running. Visit http://localhost:8080 and enjoy it! This
blog is fully functionnal. The next section section will present the way to
develop new cubes and customizing the look of your instance.


