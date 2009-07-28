.. -*- coding: utf-8 -*-

Sessions
========

There are three kinds of sessions.

* `user sessions` are the most common: they are related to users and
  carry security checks coming with user credentials

* `super sessions` are children of ordinary user sessions and allow to
  bypass security checks (they are created by calling unsafe_execute
  on a user session); this is often convenient in hooks which may
  touch data that is not directly updatable by users

* `internal sessions` have all the powers; they are also used in only a
  few situations where you don't already have an adequate session at
  hand, like: user authentication, data synchronisation in
  multi-source contexts

.. note::
  Do not confuse the session type with their connection mode, for
  instance : 'in memory' or 'pyro'.

[WRITE ME]

* authentication and management of sessions
