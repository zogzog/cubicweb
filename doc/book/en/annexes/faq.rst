.. -*- coding: utf-8 -*-

Frequently Asked Questions
==========================

[XXX 'copy answer from forum' means reusing text from
http://groups.google.com/group/google-appengine/browse_frm/thread/c9476925f5f66ec6
and
http://groups.google.com/group/google-appengine/browse_frm/thread/f48cf6099973aef5/c28cd6934dd72457
]

Generalities
````````````

Why do you use the LGPL license to prevent me from doing X ?
------------------------------------------------------------

LGPL means that *if* you redistribute your application, you need to
redistribute the changes you made to CubicWeb under the LGPL licence.

Publishing a web site has nothing to do with redistributing source
code according to the terms of the LGPL. A fair amount of companies
use modified LGPL code for internal use. And someone could publish a
*CubicWeb* component under a BSD licence for others to plug into a
LGPL framework without any problem. The only thing we are trying to
prevent here is someone taking the framework and packaging it as
closed source to his own clients.

Why does not CubicWeb have a template language ?
------------------------------------------------

There are enough template languages out there. You can use your
preferred template language if you want. [explain how to use a
template language]

*CubicWeb* does not define its own templating language as this was
not our goal. Based on our experience, we realized that
we could gain productivity by letting designers use design tools
and developpers develop without the use of the templating language
as an intermediary that could not be anyway efficient for both parties.
Python is the templating language that we use in *CubicWeb*, but again,
it does not prevent you from using a templating language.

Moreover, CubicWeb currently supports `simpletal`_ out of the box and
it is also possible to use the `cwtags`_ library to build html trees
using the `with statement`_ with more comfort than raw strings.

.. _`simpletal`: http://www.owlfish.com/software/simpleTAL/
.. _`cwtags`: http://www.cubicweb.org/project/cwtags
.. _`with statement`: http://www.python.org/dev/peps/pep-0343/

Why do you think using pure python is better than using a template language ?
-----------------------------------------------------------------------------

Python is an Object Oriented Programming language and as such it
already provides a consistent and strong architecture and syntax
a templating language would not reach.

Using Python instead of a template langage for describing the user interface
makes it to maintain with real functions/classes/contexts without the need of
learning a new dialect. By using Python, we use standard OOP techniques and
this is a key factor in a robust application.

CubicWeb looks pretty recent. Is it stable ?
--------------------------------------------

It is constantly evolving, piece by piece.  The framework has evolved since
2001 and data has been migrated from one schema to the other ever since. There
is a well-defined way to handle data and schema migration.

You can see the roadmap there:
http://www.cubicweb.org/project/cubicweb?tab=projectroadmap_tab.


Why is the RQL query language looking similar to X ?
-----------------------------------------------------

It may remind you of SQL but it is higher level than SQL, more like
SPARQL. Except that SPARQL did not exist when we started the project.
With version 3.4, CubicWeb has support for SPARQL.

The RQL language is what is going to make a difference with django-
like frameworks for several reasons.

1. accessing data is *much* easier with it. One can write complex
   queries with RQL that would be tedious to define and hard to maintain
   using an object/filter suite of method calls.

2. it offers an abstraction layer allowing your applications to run
   on multiple back-ends. That means not only various SQL backends
   (postgresql, sqlite, mysql), but also multiple databases at the
   same time, and also non-SQL data stores like LDAP directories and
   subversion/mercurial repositories (see the `vcsfile`
   component). Google App Engine is yet another supported target for
   RQL.

Which ajax library is CubicWeb using ?
--------------------------------------

CubicWeb uses jQuery and provides a few helpers on top of
that. Additionally, some jQuery plugins are provided (some are
provided in specific cubes).

Development
```````````

How to load data from a script ?
--------------------------------

The following script aims at loading data within a script assuming pyro-nsd is
running and your instance is configured with ``pyro-server=yes``, otherwise
you would not be able to use dbapi.

.. sourcecode:: python

    from cubicweb import dbapi

    cnx = dbapi.connect(database='instance-id', user='admin', password='admin')
    cur = cnx.cursor()
    for name in ('Personal', 'Professional', 'Computers'):
        cur.execute('INSERT Blog B: B name %s', name)
    cnx.commit()


How to format an entity date attribute ?
----------------------------------------

If your schema has an attribute of type Date or Datetime, you might
want to format it. First, you should define your preferred format using
the site configuration panel ``http://appurl/view?vid=systempropertiesform``
and then set ``ui.date`` and/or ``ui.datetime``.
Then in the view code, use:

.. sourcecode:: python

    self.format_date(entity.date_attribute)

What is the CubicWeb datatype corresponding to GAE datastore's UserProperty ?
-----------------------------------------------------------------------------

If you take a look at your instance schema and
click on "display detailed view of metadata" you will see that there
is a Euser entity in there. That's the one that is modeling users. The
thing that corresponds to a UserProperty is a relationship between
your entity and the Euser entity. As in:

.. sourcecode:: python

    class TodoItem(EntityType):
       text = String()
       todo_by = SubjectRelation('Euser')

[XXX check that cw handle users better by mapping Google Accounts to local Euser
entities automatically]


How do I translate an msg id defined (and translated) in another cube ?
-----------------------------------------------------------------------

You should put these translations in the `i18n/static-messages.pot`
file of your own cube.


What is `Error while publishing rest text ...` ?
------------------------------------------------

While modifying the description of an entity, you get an error message in
the instance `Error while publishing ...` for Rest text and plain text.
The server returns a traceback like as follows ::

      2008-10-06 15:05:08 - (cubicweb.rest) ERROR: error while publishing ReST text
      Traceback (most recent call last):
      File "/home/user/src/blogdemo/cubicweb/common/rest.py", line 217, in rest_publish
      File "/usr/lib/python2.5/codecs.py", line 817, in open
      file = __builtin__.open(filename, mode, buffering)
      TypeError: __init__() takes at most 3 arguments (4 given)

This can be fixed by applying the patch described in :
http://code.google.com/p/googleappengine/issues/detail?id=48

What are hooks used for ?
-------------------------

Hooks are executed around (actually before or after) events.  The
most common events are data creation, update and deletion.  They
permit additional constraint checking (those not expressible at the
schema level), pre and post computations depending on data
movements.

As such, they are a vital part of the framework.

Other kinds of hooks, called Operations, are available
for execution just before commit.

When should you define an HTML template rather than define a graphical component ?
----------------------------------------------------------------------------------

An HTML template cannot contain code, hence it is only about static
content.  A component is made of code and operations that apply on a
well defined context (request, result set). It enables much more
dynamic views.

How to update a database after a schema modification ?
------------------------------------------------------

It depends on what has been modified in the schema.

* update the permissions and properties of an entity or a relation:
  ``sync_schema_props_perms('MyEntityOrRelation')``.

* add an attribute: ``add_attribute('MyEntityType', 'myattr')``.

* add a relation: ``add_relation_definition('SubjRelation', 'MyRelation', 'ObjRelation')``.


How to create an anonymous user ?
---------------------------------

This allows to bypass authentication for your site. In the
``all-in-one.conf`` file of your instance, define the anonymous user
as follows ::

  # login of the CubicWeb user account to use for anonymous user (if you want to
  # allow anonymous)
  anonymous-user=anon

  # password of the CubicWeb user account matching login
  anonymous-password=anon

You also must ensure that this `anon` user is a registered user of
the DB backend. If not, you can create through the administation
interface of your instance by adding a user with the role `guests`.
This could be the admin account (for development
purposes, of course).

.. note::
    While creating a new instance, you can decide to allow access
    to anonymous user, which will automatically execute what is
    decribed above.


How to change the instance logo ?
------------------------------------

There are two ways of changing the logo.

1. The easiest way to use a different logo is to replace the existing
   ``logo.png`` in ``myapp/data`` by your prefered icon and refresh.
   By default all instance will look for a ``logo.png`` to be
   rendered in the logo section.

   .. image:: ../images/lax-book_06-main-template-logo_en.png

2. In your cube directory, you can specify which file to use for the logo.
   This is configurable in ``mycube/data/external_resources``: ::

     LOGO = DATADIR/path/to/mylogo.gif

   where DATADIR is ``mycube/data``.

Configuration
`````````````

How to configure a LDAP source ?
--------------------------------

Your instance's sources are defined in ``/etc/cubicweb.d/myapp/sources``.
Configuring an LDAP source is about declaring that source in your
instance configuration file such as: ::

  [ldapuser]
  adapter=ldapuser
  # ldap host
  host=myhost
  # base DN to lookup for usres
  user-base-dn=ou=People,dc=mydomain,dc=fr
  # user search scope
  user-scope=ONELEVEL
  # classes of user
  user-classes=top,posixAccount
  # attribute used as login on authentication
  user-login-attr=uid
  # name of a group in which ldap users will be by default
  user-default-group=users
  # map from ldap user attributes to cubicweb attributes
  user-attrs-map=gecos:email,uid:login

Any change applied to configuration file requires to restart your
instance.

You can find additional information in the section :ref:`LDAP`.

How to import LDAP users in |cubicweb| ?
----------------------------------------

  Here is a useful script which enables you to import LDAP users
  into your *CubicWeb* instance by running the following:

.. sourcecode:: python

    import os
    import pwd
    import sys

    from logilab.database import get_connection

    def getlogin():
        """avoid using os.getlogin() because of strange tty/stdin problems
        (man 3 getlogin)
        Another solution would be to use $LOGNAME, $USER or $USERNAME
        """
        return pwd.getpwuid(os.getuid())[0]


    try:
        database = sys.argv[1]
    except IndexError:
        print 'USAGE: python ldap2system.py <database>'
        sys.exit(1)

    if raw_input('update %s db ? [y/n]: ' % database).strip().lower().startswith('y'):
        cnx = get_connection(user=getlogin(), database=database)
        cursor = cnx.cursor()

        insert = ('INSERT INTO euser (creation_date, eid, modification_date, login, '
                  ' firstname, surname, last_login_time, upassword) '
                  "VALUES (%(mtime)s, %(eid)s, %(mtime)s, %(login)s, %(firstname)s, "
                  "%(surname)s, %(mtime)s, './fqEz5LeZnT6');")
        update = "UPDATE entities SET source='system' WHERE eid=%(eid)s;"
        cursor.execute("SELECT eid,type,source,extid,mtime FROM entities WHERE source!='system'")
        for eid, type, source, extid, mtime in cursor.fetchall():
            if type != 'CWUser':
                print "don't know what to do with entity type", type
                continue
            if source != 'ldapuser':
                print "don't know what to do with source type", source
                continue
            ldapinfos = dict(x.strip().split('=') for x in extid.split(','))
            login = ldapinfos['uid']
            firstname = ldapinfos['uid'][0].upper()
            surname = ldapinfos['uid'][1:].capitalize()
            if login != 'jcuissinat':
                args = dict(eid=eid, type=type, source=source, login=login,
                            firstname=firstname, surname=surname, mtime=mtime)
                print args
                cursor.execute(insert, args)
                cursor.execute(update, args)

        cnx.commit()
        cnx.close()


I get NoSelectableObject exceptions, how do I debug selectors ?
---------------------------------------------------------------

You just need to put the appropriate context manager around view/component
selection (one standard place in in vreg.py):

.. sourcecode:: python

    def possible_objects(self, registry, *args, **kwargs):
        """return an iterator on possible objects in a registry for this result set

        actions returned are classes, not instances
        """
        from cubicweb.selectors import traced_selection
        with traced_selection():
            for vobjects in self.registry(registry).values():
                try:
                    yield self.select(vobjects, *args, **kwargs)
                except NoSelectableObject:
                    continue

Don't forget the 'from __future__ import with_statement' at the module
top-level.

This will yield additional WARNINGs, like this::

    2009-01-09 16:43:52 - (cubicweb.selectors) WARNING: selector one_line_rset returned 0 for <class 'cubicweb.web.views.basecomponents.WFHistoryVComponent'>

Security
````````

How to reset the password for user joe ?
----------------------------------------

If you want to reset the admin password for ``myinstance``, do::

    $ cubicweb-ctl reset-admin-pwd myinstance

You need to generate a new encrypted password::

    $ python
    >>> from cubicweb.server.utils import crypt_password
    >>> crypt_password('joepass')
    'qHO8282QN5Utg'
    >>>

and paste it in the database::

    $ psql mydb
    mydb=> update cw_cwuser set cw_upassword='qHO8282QN5Utg' where cw_login='joe';
    UPDATE 1

if you're running over SQL Server, you need to use the CONVERT
function to convert the string to varbinary(255). The SQL query is
therefore::

    update cw_cwuser set cw_upassword=CONVERT(varbinary(255), 'qHO8282QN5Utg') where cw_login='joe';

Be careful, the encryption algorithm is different on Windows and on
Unix. You cannot therefore use a hash generated on Unix to fill in a
Windows database, nor the other way round. 


You can prefer use a migration script similar to this shell invocation instead::

    $ cubicweb-ctl shell <instance>
    >>> from cubicweb.server.utils import crypt_password
    >>> crypted = crypt_password('joepass')
    >>> rset = rql('Any U WHERE U is CWUser, U login "joe"')
    >>> joe = rset.get_entity(0,0)
    >>> joe.set_attributes(upassword=crypted)

The more experimented people would use RQL request directly::

    >>> rql('SET X upassword %(a)s WHERE X is CWUser, X login "joe"',
    ...     {'a': crypted})

I've just created a user in a group and it doesn't work !
---------------------------------------------------------

You are probably getting errors such as ::

  remove {'PR': 'Project', 'C': 'CWUser'} from solutions since your_user has no read access to cost

This is because you have to put your user in the "users" group. The user has to be in both groups.

How is security implemented ?
------------------------------

The basis for security is a mapping from operations to groups or
arbitrary RQL expressions. These mappings are scoped to entities and
relations.

This is an example for an Entity Type definition:

.. sourcecode:: python

    class Version(EntityType):
        """a version is defining the content of a particular project's
        release"""
        # definition of attributes is voluntarily missing
        __permissions__ = {'read': ('managers', 'users', 'guests',),
                           'update': ('managers', 'logilab', 'owners'),
                           'delete': ('managers',),
                           'add': ('managers', 'logilab',
                                   ERQLExpression('X version_of PROJ, U in_group G, '
                                                  'PROJ require_permission P, '
                                                  'P name "add_version", P require_group G'),)}

The above means that permission to read a Version is granted to any
user that is part of one of the groups 'managers', 'users', 'guests'.
The 'add' permission is granted to users in group 'managers' or
'logilab' or to users in group G, if G is linked by a permission
entity named "add_version" to the version's project.

An example for a Relation Definition (RelationType both defines a
relation type and implicitly one relation definition, on which the
permissions actually apply):

.. sourcecode:: python

    class version_of(RelationType):
        """link a version to its project. A version is necessarily linked
        to one and only one project. """
        # some lines voluntarily missing
        __permissions__ = {'read': ('managers', 'users', 'guests',),
                           'delete': ('managers', ),
                           'add': ('managers', 'logilab',
                                   RRQLExpression('O require_permission P, P name "add_version", '
                                                  'U in_group G, P require_group G'),) }

The main difference lies in the basic available operations (there is
no 'update' operation) and the usage of an RRQLExpression (rql
expression for a relation) instead of an ERQLExpression (rql
expression for an entity).

You can find additional information in the section :ref:`securitymodel`.

Is it possible to bypass security from the UI (web front) part ?
----------------------------------------------------------------

No.

Only Hooks/Operations can do that.

Can PostgreSQL and CubicWeb authentication work with kerberos ?
----------------------------------------------------------------

If you have PostgreSQL set up to accept kerberos authentication, you can set
the db-host, db-name and db-user parameters in the `sources` configuration
file while leaving the password blank. It should be enough for your
instance to connect to postgresql with a kerberos ticket.


