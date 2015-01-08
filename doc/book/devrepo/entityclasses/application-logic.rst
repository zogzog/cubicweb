How to use entities objects and adapters
----------------------------------------

The previous chapters detailed the classes and methods available to
the developer at the so-called `ORM`_ level. However they say little
about the common patterns of usage of these objects.

.. _`ORM`: http://en.wikipedia.org/wiki/Object-relational_mapping

Entities objects (and their adapters) are used in the repository and
web sides of CubicWeb. On the repository side of things, one should
manipulate them in Hooks and Operations.

Hooks and Operations provide support for the implementation of rules
such as computed attributes, coherency invariants, etc (they play the
same role as database triggers, but in a way that is independent of
the actual data sources).

So a lot of an application's business rules will be written in Hooks
(or Operations).

On the web side, views also typically operate using entity
objects. Obvious entity methods for use in views are the Dublin Core
methods like ``dc_title``. For separation of concerns reasons, one
should ensure no ui logic pervades the entities level, and also no
business logic should creep into the views.

In the duration of a transaction, entities objects can be instantiated
many times, in views and hooks, even for the same database entity. For
instance, in a classic CubicWeb deployment setup, the repository and
the web front-end are separated process communicating over the
wire. There is no way state can be shared between these processes
(there is a specific API for that). Hence, it is not possible to use
entity objects as messengers between these components of an
application. It means that an attribute set as in ``obj.x = 42``,
whether or not x is actually an entity schema attribute, has a short
life span, limited to the hook, operation or view within which the
object was built.

Setting an attribute or relation value can be done in the context of a
Hook/Operation, using the ``obj.cw_set(x=42)`` notation or a plain
RQL ``SET`` expression.

In views, it would be preferable to encapsulate the necessary logic in
a method of an adapter for the concerned entity class(es). But of
course, this advice is also reasonable for Hooks/Operations, though
the separation of concerns here is less stringent than in the case of
views.

This leads to the practical role of objects adapters: it's where an
important part of the application logic lies (the other part being
located in the Hook/Operations).

Anatomy of an entity class
--------------------------

We can look now at a real life example coming from the `tracker`_
cube. Let us begin to study the ``entities/project.py`` content.

.. sourcecode:: python

    from cubicweb.entities.adapters import ITreeAdapter

    class ProjectAdapter(ITreeAdapter):
        __select__ = is_instance('Project')
        tree_relation = 'subproject_of'

    class Project(AnyEntity):
        __regid__ = 'Project'
        fetch_attrs, cw_fetch_order = fetch_config(('name', 'description',
                                                    'description_format', 'summary'))

        TICKET_DEFAULT_STATE_RESTR = 'S name IN ("created","identified","released","scheduled")'

        def dc_title(self):
            return self.name

The fact that the `Project` entity type implements an ``ITree``
interface is materialized by the ``ProjectAdapter`` class (inheriting
the pre-defined ``ITreeAdapter`` whose ``__regid__`` is of course
``ITree``), which will be selected on `Project` entity types because
of its selector. On this adapter, we redefine the ``tree_relation``
attribute of the ``ITreeAdapter`` class.

This is typically used in views concerned with the representation of
tree-like structures (CubicWeb provides several such views).

It is important that the views themselves try not to implement this
logic, not only because such views would be hardly applyable to other
tree-like relations, but also because it is perfectly fine and useful
to use such an interface in Hooks.

In fact, Tree nature is a property of the data model that cannot be
fully and portably expressed at the level of database entities (think
about the transitive closure of the child relation). This is a further
argument to implement it at entity class level.

``fetch_attrs`` configures which attributes should be pre-fetched when using ORM
methods retrieving entity of this type. In a same manner, the ``cw_fetch_order`` is
a class method allowing to control sort order. More on this in :ref:`FetchAttrs`.

We can observe the big ``TICKET_DEFAULT_STATE_RESTR`` is a pure
application domain piece of data. There is, of course, no limitation
to the amount of class attributes of this kind.

The ``dc_title`` method provides a (unicode string) value likely to be
consumed by views, but note that here we do not care about output
encodings. We care about providing data in the most universal format
possible, because the data could be used by a web view (which would be
responsible of ensuring XHTML compliance), or a console or file
oriented output (which would have the necessary context about the
needed byte stream encoding).

.. note::

  The Dublin Core `dc_xxx` methods are not moved to an adapter as they
  are extremely prevalent in CubicWeb and assorted cubes and should be
  available for all entity types.

Let us now dig into more substantial pieces of code, continuing the
Project class.

.. sourcecode:: python

    def latest_version(self, states=('published',), reverse=None):
        """returns the latest version(s) for the project in one of the given
        states.

        when no states specified, returns the latest published version.
        """
        order = 'DESC'
        if reverse is not None:
            warn('reverse argument is deprecated',
                 DeprecationWarning, stacklevel=1)
            if reverse:
                order = 'ASC'
        rset = self.versions_in_state(states, order, True)
        if rset:
            return rset.get_entity(0, 0)
        return None

    def versions_in_state(self, states, order='ASC', limit=False):
        """returns version(s) for the project in one of the given states, sorted
        by version number.

        If limit is true, limit result to one version.
        If reverse, versions are returned from the smallest to the greatest.
        """
        if limit:
            order += ' LIMIT 1'
        rql = 'Any V,N ORDERBY version_sort_value(N) %s ' \
              'WHERE V num N, V in_state S, S name IN (%s), ' \
              'V version_of P, P eid %%(p)s' % (order, ','.join(repr(s) for s in states))
        return self._cw.execute(rql, {'p': self.eid})

.. _`tracker`: http://www.cubicweb.org/project/cubicweb-tracker/

These few lines exhibit the important properties we want to outline:

* entity code is concerned with the application domain

* it is NOT concerned with database consistency (this is the realm of
  Hooks/Operations); in other words, it assumes a consistent world

* it is NOT (directly) concerned with end-user interfaces

* however it can be used in both contexts

* it does not create or manipulate the internal object's state

* it plays freely with RQL expression as needed

* it is not concerned with internationalization

* it does not raise exceptions


