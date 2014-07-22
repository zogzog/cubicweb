Next steps
----------

- finish what was started :

    - bypass publisher.
    - tighten the error handling and get a well-behaved application
    - provide sane default policies that match current cubicweb behavior.

- identify what can be done without pushing the 'pyramid way' into cubicweb (as
  a first step for future evolutions).


Provide a ctl command
~~~~~~~~~~~~~~~~~~~~~

Add a 'pyramid' command for cubicweb-ctl that starts a cubicweb instance within
a pyramid container.

Transactions
~~~~~~~~~~~~

A common transaction handling mechanism should be used so that the connexion
can be safely used in both pyramid and cubicweb.

Reimplement the base controllers of cw
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

-   rest
-   static
-   data

Bypass cw.handle_request in most case
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use it only when no other mean works, which should provide backward compat of
old cubes for a while.
