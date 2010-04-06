.. -*- coding: utf-8 -*-

Tests
=====

.. toctree::
   :maxdepth: 1


Unit tests
----------

*CubicWeb* framework provides essentially two Python test classes in the
module `cubicweb.devtools.apptest`:

* `EnvBasedTC`, to simulate a complete environment (web + repository)
* `RepositoryBasedTC`, to simulate a repository environment only

Those two classes almost have the same interface and offer numerous
methods to write tests rapidly and efficiently.

XXX FILLME describe API

In most of the cases, you will inherit `EnvBasedTC` to write Unittest or
functional tests for your entities, views, hooks, etc...

Managing connections or users
+++++++++++++++++++++++++++++

Since unit tests are done with the SQLITE backend and this does not
support multiple connections at a time, you must be careful when
simulating security, changing users.

By default, tests run with a user with admin privileges. This
user/connection must never be closed.
qwq
Before a self.login, one has to release the connection pool in use with a self.commit, self.rollback or self.close.

When one is logged in as a normal user and wants to switch back to the admin user, one has to use self.restore_connection().

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

Do not use the references kept to the entities created with a connection from another.


Email notifications tests
-------------------------
When running tests potentially generated e-mails are not really
sent but is found in the list `MAILBOX` of module `cubicweb.devtools.apptest`.
This list is reset at each test *setUp* (by the setUp of classes `EnvBasedTC`
and `RepositoryBasedTC`).


You can test your notifications by analyzing the contents of this list, which
contains objects with two attributes:
* `recipients`, the list of recipients
* `msg`, object email.Message


Automatic testing
-----------------
XXXFILLME
