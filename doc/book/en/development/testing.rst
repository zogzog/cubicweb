.. -*- coding: utf-8 -*-

Tests
=====

.. toctree::
   :maxdepth: 1

Unit tests
----------

The *CubicWeb* framework provides the `CubicWebTC` test base class in
the module `cubicweb.devtools.testlib`.

Tests shall be put into the mycube/test directory. Additional test
data shall go into mycube/test/data.

It is much advised to write tests concerning entities methods, hooks
and operations, security. The CubicWebTC base class has convenience
methods to help test all of this.

.. note::

  In the realm of views, there is not much to do but check that the
  views are valid XHTML.  See :ref:`automatic_views_tests` for
  details. Integration of CubicWeb tests with UI testing tools such as
  `selenium`_ are currently under invesitgation.

.. _selenium: http://seleniumhq.org/projects/ide/

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

The test class defines a `setup_database` method which populates the
database with initial data. Each test of the class runs with this
pre-populated database.

The test case itself checks that an Operation does it job of
preventing cycles amongst Keyword entities.


XXX ref to advanced use case
XXX apycot plug

Managing connections or users
+++++++++++++++++++++++++++++

Since unit tests are done with the SQLITE backend and this does not
support multiple connections at a time, you must be careful when
simulating security, changing users.

By default, tests run with a user with admin privileges. This
user/connection must never be closed.

Before a self.login, one has to release the connection pool in use
with a self.commit, self.rollback or self.close.

When one is logged in as a normal user and wants to switch back to the
admin user, one has to use self.restore_connection().

Usually it looks like this:

.. sourcecode:: python

    # execute using default admin connection
    self.execute(...)
    # I want to login with another user, ensure to free admin connection pool
    # (could have used rollback but not close here, we should never close defaut admin connection)
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

XXX the new context manager ?

Email notifications tests
-------------------------

When running tests potentially generated e-mails are not really sent
but is found in the list `MAILBOX` of module
`cubicweb.devtools.testlib`.

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

.. _automatic_views_tests:

Automatic views testing
-----------------------

This is done automatically with the AutomaticWebTest class. At cube
creation time, the mycube/test/test_mycube.py file contains such a
test. The code here has to be uncommented to be usable, without
further modification.

XXX more to come


Using Pytest
````````````

.. automodule:: logilab.common.testlib
.. autoclass:: logilab.common.testlib.TestCase
   :members:

XXX pytestconf.py & options (e.g --source to use a different db
backend than sqlite)

CubicWebTC API
``````````````
.. autoclass:: cubicweb.devtools.testlib.CubicWebTC
   :members:

