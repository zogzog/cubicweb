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

   cubicweb-ctl newcube -d <target directory>

This will create a new cube ``<target directory>``.

Create an instance
-------------------

You must ensure `~/etc/cubicweb.d/` exists prior to this. On windows, the
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

Run an instance
---------------

To start an instance during development, use ::

   cubicweb-ctl pyramid [-D] [-l <log-level>] <instance-id>

without ``-D``, the instance will be start in the background, as a daemon.

See :ref:`cubicweb-ctl_pyramid` for more details.

In production, it is recommended to run CubicWeb through a WSGI server like
uWSGI or Gunicorn. See :mod:`cubicweb.pyramid` more details.

Commands to maintain instances
------------------------------

* ``upgrade``, launches the existing instances migration when a new version
  of *CubicWeb* or the cubes installed is available
* ``shell``, opens a (Python based) migration shell for manual maintenance of the instance
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
