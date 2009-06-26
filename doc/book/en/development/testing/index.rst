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

Thos two classes almost have the same interface and offers numerous methods to
write tests rapidely and efficiently.

XXX FILLME describe API

In most of the cases, you will inherit `EnvBasedTC` to write Unittest or
functional tests for your entities, views, hooks, etc...


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
