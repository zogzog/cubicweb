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


Views
-----

Goal: Have Cubicweb Views selected by pyramid.

The selection behavior should be consistent with the cw predicates weight based
priority system.

Several approaches should be studied, some less integrated than others.

Use a ViewMapper
~~~~~~~~~~~~~~~~

Here, the idea is to register a single pseudo view for each view __regid__
present in the CW registry.

The view mapper associated with these pseudo views would do a view lookup on
the CW registry first, then call it for rendering.

Pros
    *   Easy to implement

Cons
    *   Need to keep two registries in the long term
    *   Two phases lookup: once in pyramid, once in CW.
    *   A lookup is performed when pyramid assumes it is finished and
        successful, which means we do not respect the pyramid API (A
        ViewMapper is just supposed to render an already selected view)
    *   CW views are not registered directly by pyramid

I (Christophe) don't like this solution because it is too much of a workaround
and we would not use the pyramid API, just wrapping stuffs.


Use a custom IMultiView
~~~~~~~~~~~~~~~~~~~~~~~

Implements a IMultiView (see pyramid.config.views.MultiView) that lookups in
the CW registry in hits __discriminator__.

One instance of this class would be registered for each __regid__, like with
the ViewMapper-based solution.

Pros
    *   Not too difficult to implement
    *   Respect more the pyramid API: the lookup is performed at a moment it is
        expected by pyramid. In the end, pyramid will know the right view, and
        any other system looking up for a view will find an actual one, not a
        pseudo one.

Cons
    *   The CW views are not registered directly in pyramid
    *   Still doing two lookups in two different registries.


Use CW predicates in add_view (basic)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we add a "cwselect" predicate to pyramid, that makes it able to evaluate
the cubicweb predicates.

Pros
    *   We by-pass the CW registry


Cons
    *   We loose the cw predicate weigths


Use CW predicates in add_view + total ordering
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we choose to drop the runtime evaluation of the predicates weight.

Instead, we evaluate the weight of a predicate when it matches, and use that to
sort the views in the registry.

This would need only a slight change of the pyramid MultiView, which would sort
the views in this new order we compute instead of the default one.

To use this system, we would need to duplicate the view registering when the
expression has some "or" operators in it. The idea is to obtain 'and-only'
predicate expressions for add_view.

The only blocking point against that would be if some actual cw predicates
returns a variable weight depending on the context, because it would make it
impossible to pre-evaluate an expression weight if it matches.

Use CW predicates in add_view + cw predicate weight
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add runtine evalution of predicate weigths into pyramid.

No real clue on how we can to that (yet), although it will most probably
involve changes in MultiView.
