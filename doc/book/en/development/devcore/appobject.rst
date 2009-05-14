
  
The `AppObject` class
~~~~~~~~~~~~~~~~~~~~~

In general:

* we do not inherit directly from this class but from a more specific
  class such as `AnyEntity`, `EntityView`, `AnyRsetView`,
  `Action`...

* to be recordable, a subclass has to define its own register (attribute
  `__registry__`) and its identifier (attribute `id`). Usually we do not have
  to take care of the register, only the identifier `id`.

We can find a certain number of attributes and methods defined in this class
and common to all the application objects.

At the recording, the following attributes are dynamically added to
the *subclasses*:

* `vreg`, the `vregistry` of the application
* `schema`, the application schema
* `config`, the application configuration

We also find on instances, the following attributes:

* `req`, `Request` instance
* `rset`, the *result set* associated to the object if necessary
* `cursor`, rql cursor on the session


:URL handling:
  * `build_url(method=None, **kwargs)`, returns an absolute URL based on
    the given arguments. The *controller* supposed to handle the response,
    can be specified through the special parameter `method` (the connection
    is theoretically done automatically :).

  * `datadir_url()`, returns the directory of the application data
    (contains static files such as images, css, js...)

  * `base_url()`, shortcut to `req.base_url()`

  * `url_quote(value)`, version *unicode safe* of the function `urllib.quote`

:Data manipulation:

  * `etype_rset(etype, size=1)`, shortcut to `vreg.etype_rset()`

  * `eid_rset(eid, rql=None, descr=True)`, returns a *result set* object for
    the given eid
  * `entity(row, col=0)`, returns the entity corresponding to the data position
    in the *result set* associated to the object

  * `complete_entity(row, col=0, skip_bytes=True)`, is equivalent to `entity` but
    also call the method `complete()` on the entity before returning it

:Data formatting:
  * `format_date(date, date_format=None, time=False)` returns a string for a
    mx date time according to application's configuration
  * `format_time(time)` returns a string for a mx date time according to
    application's configuration

:And more...:

  * `external_resource(rid, default=_MARKER)`, access to a value defined in the
    configuration file `external_resource`

  * `tal_render(template, variables)`, renders a precompiled page template with
    variables in the given dictionary as context

.. note::
  When we inherit from `AppObject` (even not directly), you *always* have to use
  **super()** to get the methods and attributes of the superclasses, and not
  use the class identifier.
  For example, instead of writting: ::

      class Truc(PrimaryView):
          def f(self, arg1):
              PrimaryView.f(self, arg1)

  You'd better write: ::

      class Truc(PrimaryView):
          def f(self, arg1):
              super(Truc, self).f(arg1)
