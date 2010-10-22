.. -*- coding: utf-8 -*-

Tests
=====

Unit tests
----------

The *CubicWeb* framework provides the
:class:`cubicweb.devtools.testlib.CubicWebTC` test base class .

Tests shall be put into the mycube/test directory. Additional test
data shall go into mycube/test/data.

It is much advised to write tests concerning entities methods,
actions, hooks and operations, security. The
:class:`~cubicweb.devtools.testlib.CubicWebTC` base class has
convenience methods to help test all of this.

In the realm of views, automatic tests check that views are valid
XHTML. See :ref:`automatic_views_tests` for details. Since 3.9, bases
for web functional testing using `windmill
<http://www.getwindmill.com/>`_ are set. See test cases in
cubicweb/web/test/windmill and python wrapper in
cubicweb/web/test_windmill/ if you want to use this in your own cube.


Most unit tests need a live database to work against. This is achieved
by CubicWeb using automatically sqlite (bundled with Python, see
http://docs.python.org/library/sqlite3.html) as a backend.

The database is stored in the mycube/test/tmpdb,
mycube/test/tmpdb-template files. If it does not (yet) exists, it will
be built automatically when the test suit starts.

.. warning::

  Whenever the schema changes (new entities, attributes, relations)
  one must delete these two files. Changes concerned only with entity
  or relation type properties (constraints, cardinalities,
  permissions) and generally dealt with using the
  `sync_schema_props_perms()` fonction of the migration environment
  need not a database regeneration step.

.. _hook_test:

Unit test by example
````````````````````

We start with an example extracted from the keyword cube (available
from http://www.cubicweb.org/project/cubicweb-keyword).

.. sourcecode:: python

    from cubicweb.devtools.testlib import CubicWebTC
    from cubicweb import ValidationError

    class ClassificationHooksTC(CubicWebTC):

        def setup_database(self):
            req = self.request()
            group_etype = req.execute('Any X WHERE X name "CWGroup"').get_entity(0,0)
            c1 = req.create_entity('Classification', name=u'classif1',
                                   classifies=group_etype)
            user_etype = req.execute('Any X WHERE X name "CWUser"').get_entity(0,0)
            c2 = req.create_entity('Classification', name=u'classif2',
                                   classifies=user_etype)
            self.kw1 = req.create_entity('Keyword', name=u'kwgroup', included_in=c1)
            self.kw2 = req.create_entity('Keyword', name=u'kwuser', included_in=c2)

        def test_cannot_create_cycles(self):
            # direct obvious cycle
            self.assertRaises(ValidationError, self.kw1.set_relations,
                              subkeyword_of=self.kw1)
            # testing indirect cycles
            kw3 = self.execute('INSERT Keyword SK: SK name "kwgroup2", SK included_in C, '
                               'SK subkeyword_of K WHERE C name "classif1", K eid %s'
                               % self.kw1.eid).get_entity(0,0)
            self.kw1.set_relations(subkeyword_of=kw3)
            self.assertRaises(ValidationError, self.commit)

The test class defines a :meth:`setup_database` method which populates the
database with initial data. Each test of the class runs with this
pre-populated database. A commit is done automatically after the
:meth:`setup_database` call. You don't have to call it explicitely.

The test case itself checks that an Operation does it job of
preventing cycles amongst Keyword entities.

`create_entity` is a useful method, which easily allows to create an
entity. You can link this entity to others entities, by specifying as
argument, the relation name, and the entity to link, as value. In the
above example, the `Classification` entity is linked to a `CWEtype`
via the relation `classifies`. Conversely, if you are creating a
`CWEtype` entity, you can link it to a `Classification` entity, by
adding `reverse_classifies` as argument.

.. note::

   :meth:`commit` method is not called automatically in test_XXX
   methods. You have to call it explicitely if needed (notably to test
   operations). It is a good practice to call :meth:`clear_all_caches`
   on entities after a commit to avoid request cache effects.

You can see an example of security tests in the
:ref:`adv_tuto_security`.

It is possible to have these tests run continuously using `apycot`_.

.. _apycot: http://www.logilab.org/project/apycot

.. _securitytest:

Managing connections or users
+++++++++++++++++++++++++++++

Since unit tests are done with the SQLITE backend and this does not
support multiple connections at a time, you must be careful when
simulating security, changing users.

By default, tests run with a user with admin privileges. This
user/connection must never be closed.

Before a self.login, one has to release the connection pool in use
with a self.commit, self.rollback or self.close.

The `login` method returns a connection object that can be used as a
context manager:

.. sourcecode:: python

   with self.login('user1') as user:
       req = user.req
       req.execute(...)

On exit of the context manager, either a commit or rollback is issued,
which releases the connection.

When one is logged in as a normal user and wants to switch back to the
admin user without committing, one has to use
self.restore_connection().

Usage with restore_connection:

.. sourcecode:: python

    # execute using default admin connection
    self.execute(...)
    # I want to login with another user, ensure to free admin connection pool
    # (could have used rollback but not close here
    # we should never close defaut admin connection)
    self.commit()
    cnx = self.login('user')
    # execute using user connection
    self.execute(...)
    # I want to login with another user or with admin user
    self.commit();  cnx.close()
    # restore admin connection, never use cnx = self.login('admin'), it will return
    # the default admin connection and one may be tempted to close it
    self.restore_connection()

.. warning::

   Do not use the references kept to the entities created with a
   connection from another !

Email notifications tests
`````````````````````````

When running tests potentially generated e-mails are not really sent
but is found in the list `MAILBOX` of module
:mod:`cubicweb.devtools.testlib`.

You can test your notifications by analyzing the contents of this list, which
contains objects with two attributes:

* `recipients`, the list of recipients
* `msg`, object email.Message

Let us look at simple example from the ``blog`` cube.

.. sourcecode:: python

    from cubicweb.devtools.testlib import CubicWebTC, MAILBOX

    class BlogTestsCubicWebTC(CubicWebTC):
        """test blog specific behaviours"""

        def test_notifications(self):
            req = self.request()
            cubicweb_blog = req.create_entity('Blog', title=u'cubicweb',
                                description=u'cubicweb is beautiful')
            blog_entry_1 = req.create_entity('BlogEntry', title=u'hop',
                                             content=u'cubicweb hop')
            blog_entry_1.set_relations(entry_of=cubicweb_blog)
            blog_entry_2 = req.create_entity('BlogEntry', title=u'yes',
                                             content=u'cubicweb yes')
            blog_entry_2.set_relations(entry_of=cubicweb_blog)
            self.assertEquals(len(MAILBOX), 0)
            self.commit()
            self.assertEquals(len(MAILBOX), 2)
            mail = MAILBOX[0]
            self.assertEquals(mail.subject, '[data] hop')
            mail = MAILBOX[1]
            self.assertEquals(mail.subject, '[data] yes')

Visible actions tests
`````````````````````

It is easy to write unit tests to test actions which are visible to
user or to a category of users. Let's take an example in the
`conference cube`_.

.. _`conference cube`: http://www.cubicweb.org/project/cubicweb-conference
.. sourcecode:: python

    class ConferenceActionsTC(CubicWebTC):

        def setup_database(self):
            self.conf = self.create_entity('Conference',
                                           title=u'my conf',
                                           url_id=u'conf',
                                           start_on=date(2010, 1, 27),
                                           end_on = date(2010, 1, 29),
                                           call_open=True,
                                           reverse_is_chair_at=chair,
                                           reverse_is_reviewer_at=reviewer)

        def test_admin(self):
            req = self.request()
            rset = req.execute('Any C WHERE C is Conference')
            self.assertListEquals(self.pactions(req, rset),
                                  [('workflow', workflow.WorkflowActions),
                                   ('edit', confactions.ModifyAction),
                                   ('managepermission', actions.ManagePermissionsAction),
                                   ('addrelated', actions.AddRelatedActions),
                                   ('delete', actions.DeleteAction),
                                   ('generate_badge_action', badges.GenerateBadgeAction),
                                   ('addtalkinconf', confactions.AddTalkInConferenceAction)
                                   ])
            self.assertListEquals(self.action_submenu(req, rset, 'addrelated'),
                                  [(u'add Track in_conf Conference object',
                                    u'http://testing.fr/cubicweb/add/Track'
                                    u'?__linkto=in_conf%%3A%(conf)s%%3Asubject&'
                                    u'__redirectpath=conference%%2Fconf&'
                                    u'__redirectvid=' % {'conf': self.conf.eid}),
                                   ])

You just have to execute a rql query corresponding to the view you want to test,
and to compare the result of
:meth:`~cubicweb.devtools.testlib.CubicWebTC.pactions` with the list of actions
that must be visible in the interface. This is a list of tuples. The first
element is the action's `__regid__`, the second the action's class.

To test actions in submenu, you just have to test the result of
:meth:`~cubicweb.devtools.testlib.CubicWebTC.action_submenu` method. The last
parameter of the method is the action's category. The result is a list of
tuples. The first element is the action's title, and the second element the
action's url.


.. _automatic_views_tests:

Automatic views testing
-----------------------

This is done automatically with the :class:`cubicweb.devtools.testlib.AutomaticWebTest`
class. At cube creation time, the mycube/test/test_mycube.py file
contains such a test. The code here has to be uncommented to be
usable, without further modification.

The ``auto_populate`` method uses a smart algorithm to create
pseudo-random data in the database, thus enabling the views to be
invoked and tested.

Depending on the schema, hooks and operations constraints, it is not
always possible for the automatic auto_populate to proceed.

It is possible of course to completely redefine auto_populate. A
lighter solution is to give hints (fill some class attributes) about
what entities and relations have to be skipped by the auto_populate
mechanism. These are:

* `no_auto_populate`, may contain a list of entity types to skip
* `ignored_relations`, may contain a list of relation types to skip
* `application_rql`, may contain a list of rql expressions that
  auto_populate cannot guess by itself; these must yield resultsets
  against which views may be selected.

.. warning::

  Take care to not let the imported `AutomaticWebTest` in your test module
  namespace, else both your subclass *and* this parent class will be run.

Testing on a real-life database
-------------------------------

The ``CubicWebTC`` class uses the `cubicweb.devtools.ApptestConfiguration`
configuration class to setup its testing environment (database driver,
user password, application home, and so on). The `cubicweb.devtools`
module also provides a `RealDatabaseConfiguration`
class that will read a regular cubicweb sources file to fetch all
this information but will also prevent the database to be initalized
and reset between tests.

For a test class to use a specific configuration, you have to set
the `_config` class attribute on the class as in:

.. sourcecode:: python

    from cubicweb.devtools import RealDatabaseConfiguration
    from cubicweb.devtools.testlib import CubicWebTC

    class BlogRealDatabaseTC(CubicWebTC):
        _config = RealDatabaseConfiguration('blog',
                                            sourcefile='/path/to/realdb_sources')

        def test_blog_rss(self):
	    req = self.request()
	    rset = req.execute('Any B ORDERBY D DESC WHERE B is BlogEntry, '
	                       'B created_by U, U login "logilab", B creation_date D')
            self.view('rss', rset)



Testing with other cubes
------------------------

Sometimes a small component cannot be tested all by itself, so one
needs to specify other cubes to be used as part of the the unit test
suite. This is handled by the ``bootstrap_cubes`` file located under
``mycube/test/data``. One example from the `preview` cube::

 card, file, preview

The format is:

* possibly several empy lines or lines starting with ``#`` (comment lines)
* one line containing a coma separated list of cube names.

It is also possible to add a ``schema.py`` file in
``mycube/test/data``, which will be used by the testing framework,
therefore making new entity types and relations available to the
tests. 

Test APIS
---------

Using Pytest
````````````

The `pytest` utility (shipping with `logilab-common`_, which is a
mandatory dependency of CubicWeb) extends the Python unittest
functionality and is the preferred way to run the CubicWeb test
suites. Bare unittests also work the usual way.

.. _logilab-common: http://www.logilab.org/project/logilab-common

To use it, you may:

* just launch `pytest` in your cube to execute all tests (it will
  discover them automatically)
* launch `pytest unittest_foo.py` to execute one test file
* launch `pytest unittest_foo.py bar` to execute all test methods and
  all test cases whose name contain `bar`

Additionally, the `-x` option tells pytest to exit at the first error
or failure. The `-i` option tells pytest to drop into pdb whenever an
exception occurs in a test.

When the `-x` option has been used and the run stopped on a test, it
is possible, after having fixed the test, to relaunch pytest with the
`-R` option to tell it to start testing again from where it previously
failed.

Using the `TestCase` base class
```````````````````````````````

The base class of CubicWebTC is logilab.common.testlib.TestCase, which
provides a lot of convenient assertion methods.

.. autoclass:: logilab.common.testlib.TestCase
   :members:

CubicWebTC API
``````````````
.. autoclass:: cubicweb.devtools.testlib.CubicWebTC
   :members:
