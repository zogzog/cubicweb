.. -*- coding: utf-8 -*-

.. _cubes:

Cubes
-----

Standard library
~~~~~~~~~~~~~~~~

A library of standard cubes are available from `CubicWeb Forge`_
Cubes provide entities and views.

The available application entities are:

* addressbook: PhoneNumber and PostalAddress

* basket: Basket (like a shopping cart)

* blog: Blog (a *very* basic blog)

* classfolder: Folder (to organize things but grouping them in folders)

* classtags: Tag (to tag anything)

* file: File (to allow users to upload and store binary or text files)

* link: Link (to collect links to web resources)

* mailinglist: MailingList (to reference a mailing-list and the URLs
  for its archives and its admin interface)

* person: Person (easily mixed with addressbook)

* task: Task (something to be done between start and stop date)

* zone: Zone (to define places within larger places, for example a
  city in a state in a country)

The available system entities are:

* comment: Comment (to attach comment threads to entities)


Adding comments to BlogDemo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To import a cube in your application just change the line in the
``__pkginfo__.py`` file and verify that the cube you are planning
to use is listed by the command ``cubicweb-ctl list``.
For example::

    __use__ = ('comment',)

will make the ``Comment`` entity available in your ``BlogDemo``
application.

Change the schema to add a relationship between ``BlogEntry`` and
``Comment`` and you are done. Since the comment cube defines the
``comments`` relationship, adding the line::

    comments = ObjectRelation('Comment', cardinality='1*', composite='object')

to the definition of a ``BlogEntry`` will be enough.

Synchronize the data model
~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you modified your data model, you need to synchronize the
database with your model. For this purpose, `CubicWeb` provides
a very useful command ``cubicweb-ctl shell blogdemo`` which
launches an interactive migration Python shell. (see 
:ref:`cubicweb-ctl` for more details))
As you modified a relation from the `BlogEntry` schema,
run the following command:
::

  synchronize_rschema('BlogEntry')
  
You can now start your application and add comments to each 
`BlogEntry`.
