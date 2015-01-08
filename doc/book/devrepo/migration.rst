.. -*- coding: utf-8 -*-

.. _migration:

Migration
=========

One of the main design goals of *CubicWeb* was to support iterative and agile
development. For this purpose, multiple actions are provided to facilitate the
improvement of an instance, and in particular to handle the changes to be
applied to the data model, without loosing existing data.

The current version of a cube (and of cubicweb itself) is provided in the file
`__pkginfo__.py` as a tuple of 3 integers.

Migration scripts management
----------------------------

Migration scripts has to be located in the directory `migration` of your
cube and named accordingly:

::

  <version n° X.Y.Z>[_<description>]_<mode>.py

in which :

* X.Y.Z is the model version number to which the script enables to migrate.

* *mode* (between the last "_" and the extension ".py") is used for
  distributed installation. It indicates to which part
  of the application (RQL server, web server) the script applies.
  Its value could be :

  * `common`, applies to the RQL server as well as the web server and updates
    files on the hard drive (configuration files migration for example).

  * `web`, applies only to the web server and updates files on the hard drive.

  * `repository`, applies only to the RQL server and updates files on the
    hard drive.

  * `Any`, applies only to the RQL server and updates data in the database
    (schema and data migration for example).

Again in the directory `migration`, the file `depends.map` allows to indicate
that for the migration to a particular model version, you always have to first
migrate to a particular *CubicWeb* version. This file can contain comments (lines
starting with `#`) and a dependency is listed as follows: ::

  <model version n° X.Y.Z> : <cubicweb version n° X.Y.Z>

For example: ::

  0.12.0: 2.26.0
  0.13.0: 2.27.0
  # 0.14 works with 2.27 <= cubicweb <= 2.28 at least
  0.15.0: 2.28.0

Base context
------------

The following identifiers are pre-defined in migration scripts:

* `config`, instance configuration

* `interactive_mode`, boolean indicating that the script is executed in
  an interactive mode or not

* `versions_map`, dictionary of migrated versions  (key are cubes
  names, including 'cubicweb', values are (from version, to version)

* `confirm(question)`, function asking the user and returning true
  if the user answers yes, false otherwise (always returns true in
  non-interactive mode)

* `_()` is equivalent to `unicode` allowing to flag the strings to
  internationalize in the migration scripts.

In the `repository` scripts, the following identifiers are also defined:

* `commit(ask_confirm=True)`, request confirming and executing a "commit"

* `schema`, instance schema (readen from the database)

* `fsschema`, installed schema on the file system (e.g. schema of
  the updated model and cubicweb)

* `repo`, repository object

* `session`, repository session object


New cube dependencies
---------------------

If your code depends on some new cubes, you have to add them in a migration
script by using:

* `add_cube(cube, update_database=True)`, add a cube.
* `add_cubes(cubes, update_database=True)`, add a list of cubes.

The `update_database` parameter is telling if the database schema
should be updated or if only the relevant persistent property should be
inserted (for the case where a new cube has been extracted from an
existing one, so the new cube schema is actually already in there).

If some of the added cubes are already used by an instance, they'll simply be
silently skipped.


Schema migration
----------------
The following functions for schema migration are available in `repository`
scripts:

* `add_attribute(etype, attrname, attrtype=None, commit=True)`, adds a new
  attribute to an existing entity type. If the attribute type is not specified,
  then it is extracted from the updated schema.

* `drop_attribute(etype, attrname, commit=True)`, removes an attribute from an
  existing entity type.

* `rename_attribute(etype, oldname, newname, commit=True)`, renames an attribute

* `add_entity_type(etype, auto=True, commit=True)`, adds a new entity type.
  If `auto` is True, all the relations using this entity type and having a known
  entity type on the other hand will automatically be added.

* `drop_entity_type(etype, commit=True)`, removes an entity type and all the
  relations using it.

* `rename_entity_type(oldname, newname, commit=True)`, renames an entity type

* `add_relation_type(rtype, addrdef=True, commit=True)`, adds a new relation
  type. If `addrdef` is True, all the relations definitions of this type will
  be added.

* `drop_relation_type(rtype, commit=True)`, removes a relation type and all the
  definitions of this type.

* `rename_relation_type(oldname, newname, commit=True)`, renames a relation type.

* `add_relation_definition(subjtype, rtype, objtype, commit=True)`, adds a new
  relation definition.

* `drop_relation_definition(subjtype, rtype, objtype, commit=True)`, removes
  a relation definition.

* `sync_schema_props_perms(ertype=None, syncperms=True, syncprops=True, syncrdefs=True, commit=True)`,
  synchronizes properties and/or permissions on:
  - the whole schema if ertype is None
  - an entity or relation type schema if ertype is a string
  - a relation definition  if ertype is a 3-uple (subject, relation, object)

* `change_relation_props(subjtype, rtype, objtype, commit=True, **kwargs)`, changes
  properties of a relation definition by using the named parameters of the properties
  to change.

* `set_widget(etype, rtype, widget, commit=True)`, changes the widget used for the
  relation <rtype> of entity type <etype>.

* `set_size_constraint(etype, rtype, size, commit=True)`, changes the size constraints
  for the relation <rtype> of entity type <etype>.

Data migration
--------------
The following functions for data migration are available in `repository` scripts:

* `rql(rql, kwargs=None, cachekey=None, ask_confirm=True)`, executes an arbitrary RQL
  query, either to interrogate or update. A result set object is returned.

* `add_entity(etype, *args, **kwargs)`, adds a new entity of the given type.
  The attribute and relation values are specified as named positional
  arguments.

Workflow creation
-----------------

The following functions for workflow creation are available in `repository`
scripts:

* `add_workflow(label, workflowof, initial=False, commit=False, **kwargs)`, adds a new workflow
  for a given type(s)

You can find more details about workflows in the chapter :ref:`Workflow` .

Configuration migration
-----------------------

The following functions for configuration migration are available in all
scripts:

* `option_renamed(oldname, newname)`, indicates that an option has been renamed

* `option_group_change(option, oldgroup, newgroup)`, indicates that an option does not
  belong anymore to the same group.

* `option_added(oldname, newname)`, indicates that an option has been added.

* `option_removed(oldname, newname)`, indicates that an option has been deleted.

The `config` variable is an object which can be used to access the
configuration values, for reading and updating, with a dictionary-like
syntax. 

Example 1: migration script changing the variable 'sender-addr' in
all-in-one.conf. The script also checks that in that the instance is
configured with a known value for that variable, and only updates the
value in that case.

.. sourcecode:: python

 wrong_addr = 'cubicweb@loiglab.fr' # known wrong address
 fixed_addr = 'cubicweb@logilab.fr'
 configured_addr = config.get('sender-addr')
 # check that the address has not been hand fixed by a sysadmin
 if configured_addr == wrong_addr: 
     config['sender-addr'] = fixed-addr
     config.save()

Example 2: checking the value of the database backend driver, which
can be useful in case you need to issue backend-dependent raw SQL
queries in a migration script.

.. sourcecode:: python

 dbdriver  = config.sources()['system']['db-driver']
 if dbdriver == "sqlserver2005":
     # this is now correctly handled by CW :-)
     sql('ALTER TABLE cw_Xxxx ALTER COLUMN cw_name varchar(64) NOT NULL;')
     commit()
 else: # postgresql
     sync_schema_props_perms(ertype=('Xxxx', 'name', 'String'),
     syncperms=False)


Others migration functions
--------------------------
Those functions are only used for low level operations that could not be
accomplished otherwise or to repair damaged databases during interactive
session. They are available in `repository` scripts:

* `sql(sql, args=None, ask_confirm=True)`, executes an arbitrary SQL query on the system source
* `add_entity_type_table(etype, commit=True)`
* `add_relation_type_table(rtype, commit=True)`
* `uninline_relation(rtype, commit=True)`


[FIXME] Add explanation on how to use cubicweb-ctl shell
