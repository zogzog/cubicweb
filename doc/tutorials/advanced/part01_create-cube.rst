.. _TutosPhotoWebSiteCubeCreation:

Cube creation and schema definition
-----------------------------------

.. _adv_tuto_create_new_cube:

Step 1: creating a virtual environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fisrt I need a python virtual environment with cubicweb::

  virtualenv python-2.7.5_cubicweb
  . /python-2.7.5_cubicweb/bin/activate
  pip install cubicweb[etwist]


Step 2: creating a new cube for my web site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One note about my development environment: I wanted to use the packaged
version of CubicWeb and cubes while keeping my cube in the current
directory, let's say `~src/cubes`::

  cd ~src/cubes
  CW_MODE=user

I can now create the cube which will hold custom code for this web
site using::

  cubicweb-ctl newcube sytweb

Enter a short description and this will create your new cube in the
`cubicweb-sytweb` folder.


.. _adv_tuto_assemble_cubes:

Step 3: pick building blocks into existing cubes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Almost everything I want to handle in my web-site is somehow already modelized in
existing cubes that I'll extend for my need. So I'll pick the following cubes:

* `folder <https://www.cubicweb.org/project/cubicweb-folder>`_, containing the
  `Folder` entity type, which will be used as both 'album' and a way to map
  file system folders. Entities are added to a given folder using the
  `filed_under` relation.

* `file <https://www.cubicweb.org/project/cubicweb-file>`_, containing `File`
  entity type, gallery view, and a file system import utility.

* `zone <https://www.cubicweb.org/project/cubicweb-zone>`_, containing the
  `Zone` entity type for hierarchical geographical zones. Entities (including
  sub-zones) are added to a given zone using the `situated_in` relation.

* `person <https://www.cubicweb.org/project/cubicweb-person>`_, containing the
  `Person` entity type plus some basic views.

* `comment <https://www.cubicweb.org/project/cubicweb-comment>`_, providing a
  full commenting system allowing one to comment entity types supporting the
  `comments` relation by adding a `Comment` entity.

* `tag <https://www.cubicweb.org/project/cubicweb-tag>`_, providing a full
  tagging system as an easy and powerful way to classify entities supporting
  the `tags` relation by linking the to `Tag` entities. This will allows
  navigation into a large number of picture.

Ok, now I'll tell my cube requires all this by editing :file:`cubicweb-sytweb/cubicweb_sytweb/__pkginfo__.py`:

  .. sourcecode:: python

    __depends__ = {'cubicweb': '>= 3.26.7',
                   'cubicweb-file': '>= 1.9.0',
                   'cubicweb-folder': '>= 1.1.0',
                   'cubicweb-person': '>= 1.2.0',
                   'cubicweb-comment': '>= 1.2.0',
                   'cubicweb-tag': '>= 1.2.0',
                   'cubicweb-zone': None}

Notice that you can express minimal version of the cube that should be used,
`None` meaning whatever version available. All packages starting with 'cubicweb-'
will be recognized as being cube, not bare python packages.

If your cube is packaged for debian, it's a good idea to update the
`debian/control` file at the same time, so you won't forget it.

Now, I need to install all the dependencies::

  cd cubicweb-sytweb
  pip install -e .
  pip install cubicweb[etwist]
  pip install psycopg2 # for postgresql


Step 4: glue everything together in my cube's schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Put this code in :file:`cubicweb-sytweb/cubicweb_sytweb/schema.py`:

.. sourcecode:: python

    from yams.buildobjs import RelationDefinition


    class comments(RelationDefinition):
        subject = 'Comment'
        object = 'File'
        # a Comment can be on only one File
        # but a File can have several comments
        cardinality = '1*'
        composite = 'object'


    class tags(RelationDefinition):
        subject = 'Tag'
        object = 'File'


    class filed_under(RelationDefinition):
        subject = 'File'
        object = 'Folder'


    class situated_in(RelationDefinition):
        subject = 'File'
        object = 'Zone'


    class displayed_on(RelationDefinition):
        subject = 'Person'
        object = 'File'


This schema:

* allows to comment and tag on `File` entity type by adding the `comments` and
  `tags` relations. This should be all we've to do for this feature since the
  related cubes provide 'pluggable section' which are automatically displayed on
  the primary view of entity types supporting the relation.

* adds a `situated_in` relation definition so that image entities can be
  geolocalized.

* add a new relation `displayed_on` relation telling who can be seen on a
  picture.

This schema will probably have to evolve as time goes (for security handling at
least), but since the possibility to let a schema evolve is one of CubicWeb's
features (and goals), we won't worry about it for now and see that later when needed.


Step 5: creating the instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that I have a schema, I want to create an instance. To
do so using this new 'sytweb' cube, I run::

  cubicweb-ctl create sytweb sytweb_instance

For simplicity you should use the sqlite database, it won't require
configuration.

Don't forget to say "yes" to the question: `Allow anonymous access ? [y/N]:`

Hint: if you get an error while the database is initialized, you can
avoid having to answer the questions again by running::

   cubicweb-ctl db-create sytweb_instance

This will use your already configured instance and start directly from the create
database step, thus skipping questions asked by the 'create' command.

Once the instance and database are fully initialized, run ::

  cubicweb-ctl start -D sytweb_instance

to start the instance, check you can connect on it, etc... then go on
http://localhost:8080 (or with another port if you've modified it)
