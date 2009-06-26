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

Command to create a cube
------------------------

* ``newcube``, create a new cube on the file system based on the name
  given in the parameters. This command create a cube from an application
  skeleton that includes default files required for debian packaging.


Command to create an instance
-----------------------------
* ``create``, creates the files for the instance configuration
* ``db-create``, creates the system database of an instance (tables and
  extensions only)
* ``db-init``, initializes the system database of an instance
  (schema, groups, users, workflows...)

By default, those three commandes are encapsulated in ``create`` so
that they can be executed consecutively.

Command to create an instance for Google AppEngine datastore source
-------------------------------------------------------------------
* ``newgapp``, creates the configuration files for an instance

This command needs to be followed by the commands responsible for
the database initialization. As those are specific to the `datastore`,
specific Google AppEgine database, they are not available for now
in cubicweb-ctl, but they are available in the instance created.

For more details, please see :ref:`gaecontents` .

Commands to control instances
-----------------------------
* ``start``, starts one or more or all instances
* ``stop``, stops one or more or all instances
* ``restart``, restarts one or more or all instances
* ``status``, returns the status of the instance

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
  the application schema. It is recommanded to create a dump before this operation.

Commands to maintain i18n catalogs
----------------------------------
* ``i18ncubicweb``, regenerates messages catalogs of the *CubicWeb* library
* ``i18ncube``, regenerates the messages catalogs of a cube
* ``i18ninstance``, recompiles the messages catalogs of an instance.
  This is automatically done while upgrading.

See also chapter :ref:`internationalisation`.

Other commands
--------------
* ``list``, provides a list of the available configuration, cubes
  and instances.
* ``delete``, deletes an instance (configuration files and database)


Create an instance from an existing cube
````````````````````````````````````````

To create an instance from an existing cube, execute the following
command ::

   cubicweb-ctl create <cube_name> <instance_name>

This command will create the configuration files of an instance in
``~/etc/cubicweb.d/<instance_name>``.
The tool ``cubicweb-ctl`` allows you to execute the command ``db-create``
and ``db-init`` when you run ``create`` so that you can complete an
instance creation in a single command.

If you decide not to execut those commands while ``cubicweb-ctl create``,
then you will have to execute them seperately(``cubicweb-ctl db-create``,
``cubicweb-ctl db-init`` ) otherwise your installation will not be complete
and you will not be able to launch your instance.


Creation of an instance from a new cube
```````````````````````````````````````

Create first your new cube cube ::

   cubicweb-ctl newcube <mycube>

This will create a new cube in ``/path/to/forest/cubicweb/cubes/<mycube>``
for a Mercurial forest installation, or in ``/usr/share/cubicweb/cubes``
for a debian packages installation, and then create an instance as
explained just above.


