Authentication
==============

Overview
--------

A default authentication stack is provided by the :mod:`cubicweb.pyramid.auth`
module, which is included by :mod:`cubicweb.pyramid.default`.

The authentication stack is built around `pyramid_multiauth`_, and provides a
few default policies that reproduce the default cubicweb behavior.

.. note::

    Note that this module only provides an authentication policy, not the views
    that handle the login form. See :ref:`login_module`

Customize
---------

The default policies can be individually deactivated, as well as the default
authentication callback that returns the current user groups as :term:`principals`.

The following settings can be set to `False`:

-   :confval:`cubicweb.auth.update_login_time`. Activate the policy that update
    the user `login_time` when `remember` is called.
-   :confval:`cubicweb.auth.authtkt` and all its subvalues.
-   :confval:`cubicweb.auth.groups_principals`

Additionnal policies can be added by accessing the MultiAuthenticationPolicy
instance in the registry:

.. code-block:: python

    mypolicy = SomePolicy()
    authpolicy = config.registry['cubicweb.authpolicy']
    authpolicy._policies.append(mypolicy)

.. _pyramid_multiauth: https://github.com/mozilla-services/pyramid_multiauth
