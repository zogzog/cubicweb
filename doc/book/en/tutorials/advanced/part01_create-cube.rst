.. _TutosPhotoWebSiteCubeCreation:

Cube creation and schema definition
-----------------------------------

.. _adv_tuto_create_new_cube:

Step 1: creating a new cube for my web site
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One note about my development environment: I wanted to use the packaged
version of CubicWeb and cubes while keeping my cube in my user
directory, let's say `~src/cubes`.  I achieve this by setting the
following environment variables::

  CW_CUBES_PATH=~/src/cubes
  CW_MODE=user

I can now create the cube which will hold custom code for this web
site using::

  cubicweb-ctl newcube --directory=~/src/cubes sytweb


.. _adv_tuto_assemble_cubes:

Step 2: pick building blocks into existing cubes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Almost everything I want to handle in my web-site is somehow already modelized in
existing cubes that I'll extend for my need. So I'll pick the following cubes:

* `folder`, containing the `Folder` entity type, which will be used as
  both 'album' and a way to map file system folders. Entities are
  added to a given folder using the `filed_under` relation.

* `file`, containing `File` entity type, gallery view, and a file system import
  utility.

* `zone`, containing the `Zone` entity type for hierarchical geographical
  zones. Entities (including sub-zones) are added to a given zone using the
  `situated_in` relation.

* `person`, containing the `Person` entity type plus some basic views.

* `comment`, providing a full commenting system allowing one to comment entity types
  supporting the `comments` relation by adding a `Comment` entity.

* `tag`, providing a full tagging system as an easy and powerful way to classify
  entities supporting the `tags` relation by linking the to `Tag` entities. This
  will allows navigation into a large number of picture.

Ok, now I'll tell my cube requires all this by editing :file:`cubes/sytweb/__pkginfo__.py`:

  .. sourcecode:: python

    __depends__ = {'cubicweb': '>= 3.10.0',
                   'cubicweb-file': '>= 1.9.0',
		   'cubicweb-folder': '>= 1.1.0',
		   'cubicweb-person': '>= 1.2.0',
		   'cubicweb-comment': '>= 1.2.0',
		   'cubicweb-tag': '>= 1.2.0',
		   'cubicweb-zone': None}

Notice that you can express minimal version of the cube that should be used,
`None` meaning whatever version available. All packages starting with 'cubicweb-'
will be recognized as being cube, not bare python packages. You can still specify
this explicitly using instead the `__depends_cubes__` dictionary which should
contains cube's name without the prefix. So the example below would be written
as:

  .. sourcecode:: python

    __depends__ = {'cubicweb': '>= 3.10.0'}
    __depends_cubes__ = {'file': '>= 1.9.0',
		         'folder': '>= 1.1.0',
		   	 'person': '>= 1.2.0',
		   	 'comment': '>= 1.2.0',
		   	 'tag': '>= 1.2.0',
		   	 'zone': None}

If your cube is packaged for debian, it's a good idea to update the
`debian/control` file at the same time, so you won't forget it.


Step 3: glue everything together in my cube's schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. sourcecode:: python

    from yams.buildobjs import RelationDefinition

    class comments(RelationDefinition):
	subject = 'Comment'
	object = 'File'
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


Step 4: creating the instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that I have a schema, I want to create an instance. To
do so using this new 'sytweb' cube, I run::

  cubicweb-ctl create sytweb sytweb_instance

Hint: if you get an error while the database is initialized, you can
avoid having to answer the questions again by running::

   cubicweb-ctl db-create sytweb_instance

This will use your already configured instance and start directly from the create
database step, thus skipping questions asked by the 'create' command.

Once the instance and database are fully initialized, run ::

  cubicweb-ctl start sytweb_instance

to start the instance, check you can connect on it, etc...

