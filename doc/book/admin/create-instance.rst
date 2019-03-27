.. -*- coding: utf-8 -*-

Creation of your first instance
===============================

Instance creation
-----------------

Now that we created a cube, we can create an instance and access it via a web
browser. We will use a `all-in-one` configuration to simplify things ::

  cubicweb-ctl create -c all-in-one mycube myinstance

.. note::
  Please note that we created a new cube for a demo purposes but
  you could have used an existing cube available in our standard library
  such as blog or person for example.

A series of questions will be prompted to you, the default answer is usually
sufficient. You can anyway modify the configuration later on by editing
configuration files. When a login/password are requested to access the database
please use the credentials you created at the time you configured the database
(:ref:`PostgresqlConfiguration`).

It is important to distinguish here the user used to access the database and the
user used to login to the cubicweb instance. When an instance starts, it uses
the login/password for the database to get the schema and handle low level
transaction. But, when :command:`cubicweb-ctl create` asks for a manager
login/psswd of *CubicWeb*, it refers to the user you will use during the
development to administrate your web instance. It will be possible, later on,
to use this user to create other users for your final web instance.


Instance administration
-----------------------

start / stop
~~~~~~~~~~~~

When this command is completed, the definition of your instance is
located in :file:`~/etc/cubicweb.d/myinstance/*`. To launch it, you
just type ::

  cubicweb-ctl pyramid -D myinstance

The option `-D` specifies the *debug mode* : the instance is not
running in server mode and does not disconnect from the terminal,
which simplifies debugging in case the instance is not properly
launched. You can see how it looks by visiting the URL
`http://localhost:8080` (the port number depends of your
configuration). To login, please use the cubicweb administrator
login/password you defined when you created the instance.

To shutdown the instance, Crtl-C in the terminal window is enough.
If you did not use the option `-D`, then type ::

  cubicweb-ctl stop myinstance

This is it! All is settled down to start developping your data model...

.. note::

  The output of `cubicweb-ctl pyramid -D myinstance` can be
  overwhelming. It is possible to reduce the log level with the
  `--loglevel` parameter as in `cubicweb-ctl pyramid -D myinstance -l
  info` to filter out all logs under `info` gravity.

upgrade
~~~~~~~

A manual upgrade step is necessary whenever a new version of CubicWeb or
a cube is installed, in order to synchronise the instance's
configuration and schema with the new code.  The command is::

  cubicweb-ctl upgrade myinstance

A series of questions will be asked. It always starts with a proposal
to make a backup of your sources (where it applies). Unless you know
exactly what you are doing (i.e. typically fiddling in debug mode, but
definitely NOT migrating a production instance), you should answer YES
to that.

The remaining questions concern the migration steps of |cubicweb|,
then of the cubes that form the whole application, in reverse
dependency order.

In principle, if the migration scripts have been properly written and
tested, you should answer YES to all questions.

Somtimes, typically while debugging a migration script, something goes
wrong and the migration fails. Unfortunately the databse may be in an
incoherent state. You have two options here:

* fix the bug, restore the database and restart the migration process
  from scratch (quite recommended in a production environement)

* try to replay the migration up to the last successful commit, that
  is answering NO to all questions up to the step that failed, and
  finish by answering YES to the remaining questions.

