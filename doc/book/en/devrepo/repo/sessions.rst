.. -*- coding: utf-8 -*-

Sessions
========

Sessions are object carrying the `.execute` method to query the data
sources.

Kinds of sessions
-----------------

There are two kinds of sessions.

* `normal sessions` are the most common: they are related to users and
  carry security checks coming with user credentials

* `internal sessions` have all the powers; they are also used in only a
  few situations where you don't already have an adequate session at
  hand, like: user authentication, data synchronisation in
  multi-source contexts

.. note::
  Do not confuse the session type with their connection mode, for
  instance : `in memory` or `pyro`.

Normal sessions are typically named `_cw` in most appobjects or
sometimes just `session`.

Internal sessions are available from the `Repository` object and are
to be used like this:

.. sourcecode:: python
   session = self.repo.internal_session()
   try:
       # do stuff
   finally:
       session.close()

.. warning::
  Do not forget to close such a session after use for a session leak
  will quickly lead to an application crash.

Authentication and management of sessions
-----------------------------------------

The authentication process is a ballet involving a few dancers:

* through its `connect` method the top-level application object (the
  `CubicWebPublisher`) will (re-)open a session whenever a web request
  comes in; it asks the `session manager` to open a session (giving
  the web request object as context) using `open_session`

  * the session manager asks its authentication manager (which is a
    `component`) to authenticate the request (using `authenticate`)

    * the authentication manager asks, in order, to its authentication
      information retrievers, a login and an opaque object containing
      other credentials elements (calling `authentication_information`),
      giving the request object each time

      * the default retriever (bizarrely named
        `LoginPaswordRetreiver`) will in turn defer login and password
        fetching to the request object (which, depending on the
        authentication mode (`cookie` or `http`), will do the
        appropriate things and return a login and a password)

    * the authentication manager, on success, asks the `Repository`
      object to connect with the found credentials (using `connect`)

      * the repository object asks authentication to all of its
        sources which support the `CWUser` entity with the given
        credentials; when successful it can build the cwuser entity,
        from which a regular `Session` object is made; it returns the
        session id

    * the authentication manager, on success, will call back _all_
      retrievers with `authenticated` and return its authentication
      data (on failure, it will try the anonymous login or, if the
      configuration forbids it, raise an `AuthenticationError`)

