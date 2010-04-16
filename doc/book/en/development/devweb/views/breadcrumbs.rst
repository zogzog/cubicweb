Breadcrumbs
-----------

Breadcrumbs are a navigation component to situate the user in the
arborescence's site.


Display
~~~~~~~

Breadcrumbs are displayed by default in the header section (see
:ref:`the_main_template_sections`).  With the default base template,
the header section is composed by the logo, the application name,
breadcrumbs and, at the most right, the login box. Breadcrumbs are
displayed just next to the application name, thus breadcrumbs begin
with a separator.

Here is the header section of the CubicWeb's forge:

.. image:: ../../../images/breadcrumbs_header.png

There are three breadcrumbs components defined in
``cubicweb/web/views/ibreadcrumbs.py`` file:

- BreadCrumbEntityVComponent: displayed for a result set with one line
  if the entity implements the ``IBreadCrumbs`` interface.
- BreadCrumbETypeVComponent: displayed for a result set with more than
  one line, but with all entities of the same type which implement the
  ``IBreadCrumbs`` interface.
- BreadCrumbAnyRSetVComponent: displayed for any other result set.

Implementation
~~~~~~~~~~~~~~

The ``IBreadCrumbs`` interface is defined in the
``cubicweb/interfaces.py`` file. It specifies that an entity which
implements this interface must have a ``breadcrumbs`` method.

Here is the API of the ``breadcrumbs`` method:

.. automethod:: cubicweb.interfaces.IBreadCrumbs.breadcrumbs


If the breadcrumbs method return a list of entities, the
``cubicweb.web.views.ibreadcrumbs.BreadCrumbView`` is used to display
the first elements and the
``cubicweb.web.views.ibreadcrumbs.BreadCrumbTextView`` is used to
display the last one.

By default, for any entity, if recurs=True, breadcrumbs method returns
a list of entities, else a list of a simple string.

In order to see a hierarchical breadcrumbs, entities must have a
``parent`` method which returns the parent entity. By default this
method doesn't exist on entity, given that it can not be guessed.

XXX To change the default separator, you have to monkeypatch the
``BreadCrumbEntityVComponent.separator`` class attribute.

XXX  add_to_breadcrumbs = False on an EntityView
