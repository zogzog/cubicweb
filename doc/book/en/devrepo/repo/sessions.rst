.. -*- coding: utf-8 -*-

Sessions
========

Sessions are objects linked to an authenticated user.  The `Session.new_cnx`
method returns a new Connection linked to that session.

Connections
===========

Connections provide the `.execute` method to query the data sources.

Kinds of connections
--------------------

There are two kinds of connections.

* `normal connections` are the most common: they are related to users and
  carry security checks coming with user credentials

* `internal connections` have all the powers; they are also used in only a
  few situations where you don't already have an adequate session at
  hand, like: user authentication, data synchronisation in
  multi-source contexts

Normal connections are typically named `_cw` in most appobjects or
sometimes just `session`.

Internal connections are available from the `Repository` object and are
to be used like this:

.. sourcecode:: python

   with self.repo.internal_cnx() as cnx:
       do_stuff_with(cnx)
       cnx.commit()

Connections should always be used as context managers, to avoid leaks.

Authentication and management of sessions
-----------------------------------------

The authentication process is a ballet involving a few dancers:

* through its `get_session` method the top-level application object (the
  `CubicWebPublisher`) will open a session whenever a web request
  comes in; it asks the `session manager` to open a session (giving
  the web request object as context) using `open_session`

  * the session manager asks its authentication manager (which is a
    `component`) to authenticate the request (using `authenticate`)

    * the authentication manager asks, in order, to its authentication
      information retrievers, a login and an opaque object containing
      other credentials elements (calling `authentication_information`),
      giving the request object each time

      * the default retriever (named `LoginPasswordRetriever`)
        will in turn defer login and password fetching to the request
        object (which, depending on the authentication mode (`cookie`
        or `http`), will do the appropriate things and return a login
        and a password)

    * the authentication manager, on success, asks the `Repository`
      object to connect with the found credentials (using `connect`)

      * the repository object asks authentication to all of its
        sources which support the `CWUser` entity with the given
        credentials; when successful it can build the cwuser entity,
        from which a regular `Session` object is made; it returns the
        session id

        * the source in turn will delegate work to an authentifier
          class that defines the ultimate `authenticate` method (for
          instance the native source will query the database against
          the provided credentials)

    * the authentication manager, on success, will call back _all_
      retrievers with `authenticated` and return its authentication
      data (on failure, it will try the anonymous login or, if the
      configuration forbids it, raise an `AuthenticationError`)

Writing authentication plugins
------------------------------

Sometimes CubicWeb's out-of-the-box authentication schemes (cookie and
http) are not sufficient. Nowadays there is a plethora of such schemes
and the framework cannot provide them all, but as the sequence above
shows, it is extensible.

Two levels have to be considered when writing an authentication
plugin: the web client and the repository.

We invented a scenario where it makes sense to have a new plugin in
each side: some middleware will do pre-authentication and under the
right circumstances add a new HTTP `x-foo-user` header to the query
before it reaches the CubicWeb instance. For a concrete example of
this, see the `trustedauth`_ cube.

.. _`trustedauth`: http://www.cubicweb.org/project/cubicweb-trustedauth

Repository authentication plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On the repository side, it is possible to register a source
authentifier using the following kind of code:

.. sourcecode:: python

 from cubicweb.server.sources import native

 class FooAuthentifier(native.LoginPasswordAuthentifier):
     """ a source authentifier plugin
     if 'foo' in authentication information, no need to check
     password
     """
     auth_rql = 'Any X WHERE X is CWUser, X login %(login)s'

     def authenticate(self, session, login, **kwargs):
         """return CWUser eid for the given login
         if this account is defined in this source,
         else raise `AuthenticationError`
         """
         session.debug('authentication by %s', self.__class__.__name__)
         if 'foo' not in kwargs:
             return super(FooAuthentifier, self).authenticate(session, login, **kwargs)
         try:
             rset = session.execute(self.auth_rql, {'login': login})
             return rset[0][0]
         except Exception, exc:
             session.debug('authentication failure (%s)', exc)
         raise AuthenticationError('foo user is unknown to us')

Since repository authentifiers are not appobjects, we have to register
them through a `server_startup` hook.

.. sourcecode:: python

 class ServerStartupHook(hook.Hook):
     """ register the foo authenticator """
     __regid__ = 'fooauthenticatorregisterer'
     events = ('server_startup',)

     def __call__(self):
         self.debug('registering foo authentifier')
         self.repo.system_source.add_authentifier(FooAuthentifier())

Web authentication plugins
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. sourcecode:: python

 class XFooUserRetriever(authentication.LoginPasswordRetriever):
     """ authenticate by the x-foo-user http header
     or just do normal login/password authentication
     """
     __regid__ = 'x-foo-user'
     order = 0

     def authentication_information(self, req):
         """retrieve authentication information from the given request, raise
         NoAuthInfo if expected information is not found
         """
         self.debug('web authenticator building auth info')
         try:
            login = req.get_header('x-foo-user')
            if login:
                return login, {'foo': True}
            else:
                return super(XFooUserRetriever, self).authentication_information(self, req)
         except Exception, exc:
            self.debug('web authenticator failed (%s)', exc)
         raise authentication.NoAuthInfo()

     def authenticated(self, retriever, req, cnx, login, authinfo):
         """callback when return authentication information have opened a
         repository connection successfully. Take care req has no session
         attached yet, hence req.execute isn't available.

         Here we set a flag on the request to indicate that the user is
         foo-authenticated. Can be used by a selector
         """
         self.debug('web authenticator running post authentication callback')
         cnx.foo_user = authinfo.get('foo')

In the `authenticated` method we add (in an admitedly slightly hackish
way) an attribute to the connection object. This, in turn, can be used
to build a selector dispatching on the fact that the user was
preauthenticated or not.

.. sourcecode:: python

 @objectify_selector
 def foo_authenticated(cls, req, rset=None, **kwargs):
     if hasattr(req.cnx, 'foo_user') and req.foo_user:
         return 1
     return 0

Full Session and Connection API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cubicweb.server.session.Session
.. autoclass:: cubicweb.server.session.Connection
