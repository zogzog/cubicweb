.. _advanced_tutorial:

Building a photo gallery with CubicWeb
======================================

Desired features
----------------

* basically a photo gallery

* photo stored on the file system and displayed dynamically through a web interface

* navigation through folder (album), tags, geographical zone, people on the
  picture... using facets

* advanced security (not everyone can see everything). More on this later.


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

* `file`, containing `File` and `Image` entity types, gallery view,
  and a file system import utility.

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

    __depends__ = {'cubicweb': '>= 3.8.0',
                   'cubicweb-file': '>= 1.2.0',
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

    __depends__ = {'cubicweb': '>= 3.8.0'}
    __depends_cubes__ = {'file': '>= 1.2.0',
		         'folder': '>= 1.1.0',
		   	 'person': '>= 1.2.0',
		   	 'comment': '>= 1.2.0',
		   	 'tag': '>= 1.2.0',
		   	 'zone': None}


Step 3: glue everything together in my cube's schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. sourcecode:: python

    from yams.buildobjs import RelationDefinition

    class comments(RelationDefinition):
	subject = 'Comment'
	object = ('File', 'Image')
	cardinality = '1*'
	composite = 'object'

    class tags(RelationDefinition):
	subject = 'Tag'
	object = ('File', 'Image')

    class filed_under(RelationDefinition):
	subject = ('File', 'Image')
	object = 'Folder'

    class situated_in(RelationDefinition):
	subject = 'Image'
	object = 'Zone'

    class displayed_on(RelationDefinition):
	subject = 'Person'
	object = 'Image'


This schema:

* allows to comment and tag on `File` and `Image` entity types by adding the
  `comments` and `tags` relations. This should be all we've to do for this
  feature since the related cubes provide 'pluggable section' which are
  automatically displayed on the primary view of entity types supporting the
  relation.

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


Security, testing and migration
-------------------------------

This part will cover various topics:

* configuring security
* migrating existing instance
* writing some unit tests

Here is the ``read`` security model I want:

* folders, files, images and comments should have one of the following visibility:

  - ``public``, everyone can see it
  - ``authenticated``, only authenticated users can see it
  - ``restricted``, only a subset of authenticated users can see it

* managers (e.g. me) can see everything
* only authenticated users can see people
* everyone can see classifier entities, such as tag and zone

Also, unless explicitly specified, the visibility of an image should be the same as
its parent folder, as well as visibility of a comment should be the same as the
commented entity. If there is no parent entity, the default visibility is
``authenticated``.

Regarding write security, that's much easier:
* anonymous can't write anything
* authenticated users can only add comment
* managers will add the remaining stuff

Now, let's implement that!

Proper security in CubicWeb is done at the schema level, so you don't have to
bother with it in views: users will only see what they can see automatically.

.. _adv_tuto_security:

Step 1: configuring security into the schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In schema, you can grant access according to groups, or to some RQL expressions:
users get access if the expression returns some results. To implement the read
security defined earlier, groups are not enough, we'll need some RQL expression. Here
is the idea:

* add a `visibility` attribute on Folder, Image and Comment, which may be one of
  the value explained above

* add a `may_be_read_by` relation from Folder, Image and Comment to users,
  which will define who can see the entity

* security propagation will be done in hook.

So the first thing to do is to modify my cube's schema.py to define those
relations:

.. sourcecode:: python

    from yams.constraints import StaticVocabularyConstraint

    class visibility(RelationDefinition):
	subject = ('Folder', 'File', 'Image', 'Comment')
	object = 'String'
	constraints = [StaticVocabularyConstraint(('public', 'authenticated',
						   'restricted', 'parent'))]
	default = 'parent'
	cardinality = '11' # required

    class may_be_read_by(RelationDefinition):
        __permissions__ = {
	    'read':   ('managers', 'users'),
	    'add':    ('managers',),
	    'delete': ('managers',),
	    }

	subject = ('Folder', 'File', 'Image', 'Comment',)
	object = 'CWUser'

We can note the following points:

* we've added a new `visibility` attribute to folder, file, image and comment
  using a `RelationDefinition`

* `cardinality = '11'` means this attribute is required. This is usually hidden
  under the `required` argument given to the `String` constructor, but we can
  rely on this here (same thing for StaticVocabularyConstraint, which is usually
  hidden by the `vocabulary` argument)

* the `parent` possible value will be used for visibility propagation

* think to secure the `may_be_read_by` permissions, else any user can add/delte it
  by default, which somewhat breaks our security model...

Now, we should be able to define security rules in the schema, based on these new
attribute and relation. Here is the code to add to *schema.py*:

.. sourcecode:: python

    from cubicweb.schema import ERQLExpression

    VISIBILITY_PERMISSIONS = {
	'read':   ('managers',
		   ERQLExpression('X visibility "public"'),
		   ERQLExpression('X may_be_read_by U')),
	'add':    ('managers',),
	'update': ('managers', 'owners',),
	'delete': ('managers', 'owners'),
	}
    AUTH_ONLY_PERMISSIONS = {
	    'read':   ('managers', 'users'),
	    'add':    ('managers',),
	    'update': ('managers', 'owners',),
	    'delete': ('managers', 'owners'),
	    }
    CLASSIFIERS_PERMISSIONS = {
	    'read':   ('managers', 'users', 'guests'),
	    'add':    ('managers',),
	    'update': ('managers', 'owners',),
	    'delete': ('managers', 'owners'),
	    }

    from cubes.folder.schema import Folder
    from cubes.file.schema import File, Image
    from cubes.comment.schema import Comment
    from cubes.person.schema import Person
    from cubes.zone.schema import Zone
    from cubes.tag.schema import Tag

    Folder.__permissions__ = VISIBILITY_PERMISSIONS
    File.__permissions__ = VISIBILITY_PERMISSIONS
    Image.__permissions__ = VISIBILITY_PERMISSIONS
    Comment.__permissions__ = VISIBILITY_PERMISSIONS.copy()
    Comment.__permissions__['add'] = ('managers', 'users',)
    Person.__permissions__ = AUTH_ONLY_PERMISSIONS
    Zone.__permissions__ = CLASSIFIERS_PERMISSIONS
    Tag.__permissions__ = CLASSIFIERS_PERMISSIONS

What's important in there:

* `VISIBILITY_PERMISSIONS` provides read access to managers group, if
  `visibility` attribute's value is 'public', or if user (designed by the 'U'
  variable in the expression) is linked to the entity (the 'X' variable) through
  the `may_read` permission

* we modify permissions of the entity types we use by importing them and
  modifying their `__permissions__` attribute

* notice the `.copy()`: we only want to modify 'add' permission for `Comment`,
  not for all entity types using `VISIBILITY_PERMISSIONS`!

* the remaining part of the security model is done using regular groups:

  - `users` is the group to which all authenticated users will belong
  - `guests` is the group of anonymous users


.. _adv_tuto_security_propagation:

Step 2: security propagation in hooks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To fullfill the requirements, we have to implement::

  Also, unless explicity specified, visibility of an image should be the same as
  its parent folder, as well as visibility of a comment should be the same as the
  commented entity.

This kind of `active` rule will be done using CubicWeb's hook
system. Hooks are triggered on database event such as addition of new
entity or relation.

The tricky part of the requirement is in *unless explicitly specified*, notably
because when the entity is added, we don't know yet its 'parent'
entity (e.g. Folder of an Image, Image commented by a Comment). To handle such things,
CubicWeb provides `Operation`, which allow to schedule things to do at commit time.

In our case we will:

* on entity creation, schedule an operation that will set default visibility

* when a "parent" relation is added, propagate parent's visibility unless the
  child already has a visibility set

Here is the code in cube's *hooks.py*:

.. sourcecode:: python

    from cubicweb.selectors import is_instance
    from cubicweb.server import hook

    class SetVisibilityOp(hook.Operation):
	def precommit_event(self):
	    for eid in self.session.transaction_data.pop('pending_visibility'):
		entity = self.session.entity_from_eid(eid)
		if entity.visibility == 'parent':
		    entity.set_attributes(visibility=u'authenticated')

    class SetVisibilityHook(hook.Hook):
	__regid__ = 'sytweb.setvisibility'
	__select__ = hook.Hook.__select__ & is_instance('Folder', 'File', 'Image', 'Comment')
	events = ('after_add_entity',)
	def __call__(self):
	    hook.set_operation(self._cw, 'pending_visibility', self.entity.eid,
			       SetVisibilityOp)

    class SetParentVisibilityHook(hook.Hook):
	__regid__ = 'sytweb.setparentvisibility'
	__select__ = hook.Hook.__select__ & hook.match_rtype('filed_under', 'comments')
	events = ('after_add_relation',)

	def __call__(self):
	    parent = self._cw.entity_from_eid(self.eidto)
	    child = self._cw.entity_from_eid(self.eidfrom)
	    if child.visibility == 'parent':
		child.set_attributes(visibility=parent.visibility)

Notice:

* hooks are application objects, hence have selectors that should match entity or
  relation types to which the hook applies. To match a relation type, we use the
  hook specific `match_rtype` selector.

* usage of `set_operation`: instead of adding an operation for each added entity,
  set_operation allows to create a single one and to store entity's eids to be
  processed in session's transaction data. This is a good pratice to avoid heavy
  operations manipulation cost when creating a lot of entities in the same
  transaction.

* the `precommit_event` method of the operation will be called at transaction's
  commit time.

* in a hook, `self._cw` is the repository session, not a web request as usually
  in views

* according to hook's event, you have access to different attributes on the hook
  instance. Here:

  - `self.entity` is the newly added entity on 'after_add_entity' events

  - `self.eidfrom` / `self.eidto` are the eid of the subject / object entity on
    'after_add_relatiohn' events (you may also get the relation type using
    `self.rtype`)

The `parent` visibility value is used to tell "propagate using parent security"
because we want that attribute to be required, so we can't use None value else
we'll get an error before we get any chance to propagate...

Now, we also want to propagate the `may_be_read_by` relation. Fortunately,
CubicWeb provides some base hook classes for such things, so we only have to add
the following code to *hooks.py*:

.. sourcecode:: python

    # relations where the "parent" entity is the subject
    S_RELS = set()
    # relations where the "parent" entity is the object
    O_RELS = set(('filed_under', 'comments',))

    class AddEntitySecurityPropagationHook(hook.PropagateSubjectRelationHook):
	"""propagate permissions when new entity are added"""
	__regid__ = 'sytweb.addentity_security_propagation'
	__select__ = (hook.PropagateSubjectRelationHook.__select__
		      & hook.match_rtype_sets(S_RELS, O_RELS))
	main_rtype = 'may_be_read_by'
	subject_relations = S_RELS
	object_relations = O_RELS

    class AddPermissionSecurityPropagationHook(hook.PropagateSubjectRelationAddHook):
	"""propagate permissions when new entity are added"""
	__regid__ = 'sytweb.addperm_security_propagation'
	__select__ = (hook.PropagateSubjectRelationAddHook.__select__
		      & hook.match_rtype('may_be_read_by',))
	subject_relations = S_RELS
	object_relations = O_RELS

    class DelPermissionSecurityPropagationHook(hook.PropagateSubjectRelationDelHook):
	__regid__ = 'sytweb.delperm_security_propagation'
	__select__ = (hook.PropagateSubjectRelationDelHook.__select__
		      & hook.match_rtype('may_be_read_by',))
	subject_relations = S_RELS
	object_relations = O_RELS

* the `AddEntitySecurityPropagationHook` will propagate the relation
  when `filed_under` or `comments` relations are added

  - the `S_RELS` and `O_RELS` set as well as the `match_rtype_sets` selector are
    used here so that if my cube is used by another one, it'll be able to
    configure security propagation by simply adding relation to one of the two
    sets.

* the two others will propagate permissions changes on parent entities to
  children entities


.. _adv_tuto_tesing_security:

Step 3: testing our security
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Security is tricky. Writing some tests for it is a very good idea. You should
even write them first, as Test Driven Development recommends!

Here is a small test case that will check the basis of our security
model, in *test/unittest_sytweb.py*:

.. sourcecode:: python

    from cubicweb.devtools.testlib import CubicWebTC
    from cubicweb import Binary

    class SecurityTC(CubicWebTC):

	def test_visibility_propagation(self):
	    # create a user for later security checks
	    toto = self.create_user('toto')
	    # init some data using the default manager connection
	    req = self.request()
	    folder = req.create_entity('Folder',
				       name=u'restricted',
				       visibility=u'restricted')
	    photo1 = req.create_entity('Image',
				       data_name=u'photo1.jpg',
				       data=Binary('xxx'),
				       filed_under=folder)
	    self.commit()
	    photo1.clear_all_caches() # good practice, avoid request cache effects
	    # visibility propagation
	    self.assertEquals(photo1.visibility, 'restricted')
	    # unless explicitly specified
	    photo2 = req.create_entity('Image',
				       data_name=u'photo2.jpg',
				       data=Binary('xxx'),
				       visibility=u'public',
				       filed_under=folder)
	    self.commit()
	    self.assertEquals(photo2.visibility, 'public')
	    # test security
	    self.login('toto')
	    req = self.request()
	    self.assertEquals(len(req.execute('Image X')), 1) # only the public one
	    self.assertEquals(len(req.execute('Folder X')), 0) # restricted...
	    # may_be_read_by propagation
	    self.restore_connection()
	    folder.set_relations(may_be_read_by=toto)
	    self.commit()
	    photo1.clear_all_caches()
	    self.failUnless(photo1.may_be_read_by)
	    # test security with permissions
	    self.login('toto')
	    req = self.request()
	    self.assertEquals(len(req.execute('Image X')), 2) # now toto has access to photo2
	    self.assertEquals(len(req.execute('Folder X')), 1) # and to restricted folder

    if __name__ == '__main__':
	from logilab.common.testlib import unittest_main
	unittest_main()

It's not complete, but show most things you'll want to do in tests: adding some
content, creating users and connecting as them in the test, etc...

To run it type:

.. sourcecode:: bash

    $ pytest unittest_sytweb.py
    ========================  unittest_sytweb.py  ========================
    -> creating tables [....................]
    -> inserting default user and default groups.
    -> storing the schema in the database [....................]
    -> database for instance data initialized.
    .
    ----------------------------------------------------------------------
    Ran 1 test in 22.547s

    OK


The first execution is taking time, since it creates a sqlite database for the
test instance. The second one will be much quicker:

.. sourcecode:: bash
    
    $ pytest unittest_sytweb.py
    ========================  unittest_sytweb.py  ========================
    .
    ----------------------------------------------------------------------
    Ran 1 test in 2.662s

    OK

If you do some changes in your schema, you'll have to force regeneration of that
database. You do that by removing the tmpdb files before running the test: ::

    $ rm data/tmpdb*


.. Note::
  pytest is a very convenient utility used to control test execution. It is available from the `logilab-common`_ package.

.. _`logilab-common`: http://www.logilab.org/project/logilab-common

.. _adv_tuto_migration_script:

Step 4: writing the migration script and migrating the instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prior to those changes, I  created an instance, feeded it with some data, so I
don't want to create a new one, but to migrate the existing one. Let's see how to
do that.

Migration commands should be put in the cube's *migration* directory, in a
file named file:`<X.Y.Z>_Any.py` ('Any' being there mostly for historical reason).

Here I'll create a *migration/0.2.0_Any.py* file containing the following
instructions:

.. sourcecode:: python

  add_relation_type('may_be_read_by')
  add_relation_type('visibility')
  sync_schema_props_perms()

Then I update the version number in cube's *__pkginfo__.py* to 0.2.0. And
that's it! Those instructions will:

* update the instance's schema by adding our two new relations and update the
  underlying database tables accordingly (the two first instructions)

* update schema's permissions definition (the last instruction)


To migrate my instance I simply type::

   cubicweb-ctl upgrade sytweb

I'll then be asked some questions to do the migration step by step. You should say
YES when it asks if a backup of your database should be done, so you can get back
to initial state if anything goes wrong...

