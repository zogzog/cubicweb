Breadcrumbs
-----------

Breadcrumbs are a navigation component to help the user locate himself
along a path of entities.

Display
~~~~~~~

Breadcrumbs are displayed by default in the header section (see
:ref:`the_main_template_sections`).  With the default main template,
the header section is composed by the logo, the application name,
breadcrumbs and, at the most right, the login box. Breadcrumbs are
displayed just next to the application name, thus they begin with a
separator.

Here is the header section of the CubicWeb's forge:

.. image:: ../../../images/breadcrumbs_header.png

There are three breadcrumbs components defined in
:mod:`cubicweb.web.views.ibreadcrumbs`:

- `BreadCrumbEntityVComponent`: displayed for a result set with one line
  if the entity is adaptable to ``IBreadCrumbsAdapter``.
- `BreadCrumbETypeVComponent`: displayed for a result set with more than
  one line, but with all entities of the same type which can adapt to
  ``IBreadCrumbsAdapter``.
- `BreadCrumbAnyRSetVComponent`: displayed for any other result set.

Building breadcrumbs
~~~~~~~~~~~~~~~~~~~~

The ``IBreadCrumbsAdapter`` adapter is defined in the
:mod:`cubicweb.web.views.ibreadcrumbs` module. It specifies that an
entity which implements this interface must have a ``breadcrumbs`` and
a ``parent_entity`` method. A default implementation for each is
provided. This implementation expoits the ITreeAdapter.

.. note::

   Redefining the breadcrumbs is the hammer way to do it. Another way
   is to define an `ITreeAdapter` adapter on an entity type. If
   available, it will be used to compute breadcrumbs.

Here is the API of the ``IBreadCrumbsAdapter`` class:

.. automethod:: cubicweb.web.views.ibreadcrumbs.IBreadCrumbsAdapter.parent_entity
.. automethod:: cubicweb.web.views.ibreadcrumbs.IBreadCrumbsAdapter.breadcrumbs

If the breadcrumbs method return a list of entities, the
``cubicweb.web.views.ibreadcrumbs.BreadCrumbView`` is used to display
the elements.

By default, for any entity, if recurs=True, breadcrumbs method returns
a list of entities, else a list of a simple string.

In order to see a hierarchical breadcrumbs, entities must have a
``parent`` method which returns the parent entity. By default this
method doesn't exist on entity, given that it can not be guessed.
