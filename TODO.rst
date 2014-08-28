Next steps
----------

Provide a ctl command
~~~~~~~~~~~~~~~~~~~~~

Add a 'pyramid' command for cubicweb-ctl that starts a cubicweb instance within
a pyramid container.

Transactions
~~~~~~~~~~~~

A common transaction handling mechanism should be used so that the connexion
can be safely used in both pyramid and cubicweb.

Authentication
~~~~~~~~~~~~~~

- Use cw as an authentication provider for the pyramid application.
- allow the cw application to use pyramid for getting user identity.

Cubicweb views
~~~~~~~~~~~~~~

Provide a simple api to call cubicweb views within pyramid views.

Error handling
~~~~~~~~~~~~~~

Have pyramid handle errors (with cubicweb views if wanted) so that we can use
the debuging tools.

Reimplement the base controllers of cw
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   rest
-   static
-   data

Bypass cw.handle_request in most case
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use it only when no other mean works, which should provide backward compat of
old cubes for a while.
