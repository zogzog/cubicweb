.. -*- coding: utf-8 -*-

Frequently Asked Questions
==========================

[XXX 'copy answer from forum' means reusing text from
http://groups.google.com/group/google-appengine/browse_frm/thread/c9476925f5f66ec6
and
http://groups.google.com/group/google-appengine/browse_frm/thread/d791ce17e2716147/eb078f8cfe8426e0
and
http://groups.google.com/group/google-appengine/browse_frm/thread/f48cf6099973aef5/c28cd6934dd72457
]

* Why does not CubicWeb have a template language ?

  There are enough template languages out there. You can use your
  preferred template language if you want. [explain how to use a
  template language]

  `CubicWeb` does not define its own templating language as this was
  not our goal. Based on our experience, we realized that
  we could gain productivity by letting designers use design tools
  and developpers develop without the use of the templating language
  as an intermediary that could not be anyway efficient for both parties.
  Python is the templating language that we use in `CubicWeb`, but again,
  it does not prevent you from using a templating language.

  The reason template languages are not used in this book is that
  experience has proved us that using pure python was less cumbersome.

* Why do you think using pure python is better than using a template language ?

  Python is an Object Oriented Programming language and as such it
  already provides a consistent and strong architecture and syntax
  a templating language would not reach.

  When doing development, you need a real language and template
  languages are not real languages.

  Using Python enables developing applications for which code is
  easier to maintain with real functions/classes/contexts
  without the need of learning a new dialect. By using Python,
  we use standard OOP techniques and this is a key factor in a
  robust application.

* Why do you use the GPL license to prevent me from doing X ?

  GPL means that *if* you redistribute your application, you need to
  redistribute it *and* the changes you made *and* the code _linked_
  to it under the GPL licence.

  Publishing a web site has nothing to do with redistributing
  source code. A fair amount of companies use modified GPL code
  for internal use. And someone could publish a `CubicWeb` component
  under a BSD licence for others to plug into a GPL framework without
  any problem. The only thing we are trying to prevent here is someone
  taking the framework and packaging it as closed source to his own
  clients.


* CubicWeb looks pretty recent. Is it stable ?

  It is constantly evolving, piece by piece.  The framework has
  evolved over the past seven years and data has been migrated from
  one schema to the other ever since. There is a well-defined way to
  handle data and schema migration.

* Why is the RQL query language looking similar to X ?

  It may remind you of SQL but it is higher level than SQL, more like
  SPARQL. Except that SPARQL did not exist when we started the project.
  Having SPARQL has a query language has been in our backlog for years.

  That RQL language is what is going to make a difference with django-
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

[copy answer from forum, explain why similar to sparql and why better
  than django and SQL]

* which ajax library

  [we use jquery and things on top of that]

* `Error while publishing rest text ...`

  While modifying the description of an entity, you get an error message in
  the application `Error while publishing ...` for Rest text and plain text.
  The server returns a traceback like as follows ::

      2008-10-06 15:05:08 - (cubicweb.rest) ERROR: error while publishing ReST text
      Traceback (most recent call last):
      File "/home/user/src/blogdemo/cubicweb/common/rest.py", line 217, in rest_publish
      File "/usr/lib/python2.5/codecs.py", line 817, in open
      file = __builtin__.open(filename, mode, buffering)
      TypeError: __init__() takes at most 3 arguments (4 given)


  This can be fixed by applying the patch described in :
  http://code.google.com/p/googleappengine/issues/detail?id=48

* What are hooks used for?

  Hooks are executed around (actually before or after) events.  The
  most common events are data creation, update and deletion.  They
  permit additional constraint checking (those not expressible at the
  schema level), pre and post computations depending on data
  movements.

  As such, they are a vital part of the framework.

  Other kinds of hooks, called Operations, are available
  for execution just before commit.

* When should you define an HTML template rather than define a graphical component?

  An HTML template cannot contain code, hence it is only about static
  content.  A component is made of code and operations that apply on a
  well defined context (request, result set). It enables much more
  dynamic views.

* What is the difference between `AppRsetObject` and `AppObject` ?

  `AppRsetObject` instances are selected on a request and a result
  set. `AppObject` instances are directly selected by id.

* How to update a database after a schema modification?

  It depends on what has been modified in the schema.

  * Update of an attribute permissions and properties: 
    ``synchronize_eschema('MyEntity')``.

  * Update of a relation permissions and properties: 
    ``synchronize_rschema('MyRelation')``.

  * Add an attribute: ``add_attribute('MyEntityType', 'myattr')``.

  * Add a relation: ``add_relation_definition('SubjRelation', 'MyRelation', 'ObjRelation')``.


* How to create an anonymous user?

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


* How to change the application logo?

  There are two ways of changing the logo.

  1. The easiest way to use a different logo is to replace the existing
     ``logo.png`` in ``myapp/data`` by your prefered icon and refresh.
     By default all application will look for a ``logo.png`` to be
     rendered in the logo section.

     .. image:: ../images/lax-book.06-main-template-logo.en.png

  2. In your cube directory, you can specify which file to use for the logo.
     This is configurable in ``mycube/data/external_resources``: ::

       LOGO = DATADIR/path/to/mylogo.gif

     where DATADIR is ``mycubes/data``.

* How to configure LDAP source?

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
  application.

* I get NoSelectableObject exceptions: how do I debug selectors ?

  You just need to put the appropriate context manager around view/component
  selection: ::

    from cubicweb.common.selectors import traced_selection
    with traced_selection():
        comp = self.vreg.select_object('contentnavigation', 'wfhistory',
                                       self.req, rset, context='navcontentbottom')

  This will yield additional WARNINGs, like this: ::

    2009-01-09 16:43:52 - (cubicweb.selectors) WARNING: selector one_line_rset returned 0 for <class 'cubicweb.web.views.basecomponents.WFHistoryVComponent'>

* How to format an entity date attribute?

  If your schema has an attribute of type Date or Datetime, you might
  want to format it. First, you should define your preferred format using
  the site configuration panel ``http://appurl/view?vid=systemepropertiesform``
  and then set ``ui.date`` and/or ``ui.datetime``.
  Then in the view code, use::
    
    self.format_date(entity.date_attribute)
