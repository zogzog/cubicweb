.. -*- coding: utf-8 -*-

.. _cubicweb-ctl:

``cubicweb-ctl`` tool
=====================

`cubicweb-ctl` is the swiss knife to manage *CubicWeb* instances.
The general syntax is ::

  cubicweb-ctl <command> [options command] <arguments commands>

To view available commands ::

  cubicweb-ctl
  cubicweb-ctl --help

Please note that the commands available depends on the *CubicWeb* packages
and cubes that have been installed.

To view the help menu on specific command ::

  cubicweb-ctl <command> --help

Listing available cubes and instance
-------------------------------------

* ``list``, provides a list of the available configuration, cubes
  and instances.


Creation of a new cube
-----------------------

Create your new cube cube ::

   cubicweb-ctl newcube

This will create a new cube in
``/path/to/forest/cubicweb/cubes/<mycube>`` for a Mercurial forest
installation, or in ``/usr/share/cubicweb/cubes`` for a debian
packages installation.

Create an instance
-------------------

You must ensure `~/cubicweb.d/` exists prior to this. On windows, the
'~' part will probably expand to 'Documents and Settings/user'.

To create an instance from an existing cube, execute the following
command ::

   cubicweb-ctl create <cube_name> <instance_name>

This command will create the configuration files of an instance in
``~/etc/cubicweb.d/<instance_name>``.

The tool ``cubicweb-ctl`` executes the command ``db-create`` and
``db-init`` when you run ``create`` so that you can complete an
instance creation in a single command. But of course it is possible
to issue these separate commands separately, at a later stage.

Command to create/initialize an instance database
-------------------------------------------------

* ``db-create``, creates the system database of an instance (tables and
  extensions only)
* ``db-init``, initializes the system database of an instance
  (schema, groups, users, workflows...)

Commands to control instances
-----------------------------

* ``start``, starts one or more or all instances

of special interest::

  start -D

will start in debug mode (under windows, starting without -D will not
work; you need instead to setup your instance as a service).

* ``stop``, stops one or more or all instances
* ``restart``, restarts one or more or all instances
* ``status``, returns the status of the instance(s)

Commands to maintain instances
------------------------------

* ``upgrade``, launches the existing instances migration when a new version
  of *CubicWeb* or the cubes installed is available
* ``shell``, opens a migration shell for manual maintenance of the instance
* ``db-dump``, creates a dump of the system database
* ``db-restore``, restores a dump of the system database
* ``db-check``, checks data integrity of an instance. If the automatic correction
  is activated, it is recommanded to create a dump before this operation.
* ``schema-sync``, synchronizes the persistent schema of an instance with
  the instance schema. It is recommanded to create a dump before this operation.

Commands to maintain i18n catalogs
----------------------------------
* ``i18ncubicweb``, regenerates messages catalogs of the *CubicWeb* library
* ``i18ncube``, regenerates the messages catalogs of a cube
* ``i18ninstance``, recompiles the messages catalogs of an instance.
  This is automatically done while upgrading.

See also chapter :ref:`internationalization`.

Other commands
--------------
* ``delete``, deletes an instance (configuration files and database)

Command to create an instance for Google AppEngine datastore source
-------------------------------------------------------------------
* ``newgapp``, creates the configuration files for an instance

This command needs to be followed by the commands responsible for
the database initialization. As those are specific to the `datastore`,
specific Google AppEgine database, they are not available for now
in cubicweb-ctl, but they are available in the instance created.

For more details, please see :ref:`GoogleAppEngineSource` .
