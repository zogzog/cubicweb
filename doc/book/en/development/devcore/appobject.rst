

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

At recording time, the following attributes are dynamically added to
the *subclasses*:

* `vreg`, the `vregistry` of the instance
* `schema`, the instance schema
* `config`, the instance configuration

We also find on instances, the following attributes:

* `req`, `Request` instance
* `rset`, the *result set* associated to the object if necessary

:URL handling:
  * `build_url(*args, **kwargs)`, returns an absolute URL based on the
    given arguments. The *controller* supposed to handle the response,
    can be specified through the first positional parameter (the
    connection is theoretically done automatically :).

:Data manipulation:

  * `entity(row, col=0)`, returns the entity corresponding to the data position
    in the *result set* associated to the object

  * `complete_entity(row, col=0, skip_bytes=True)`, is equivalent to `entity` but
    also call the method `complete()` on the entity before returning it

:Data formatting:
  * `format_date(date, date_format=None, time=False)` returns a string for a
    date time according to instance's configuration
  * `format_time(time)` returns a string for a date time according to
    instance's configuration

:And more...:

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

  You must write: ::

      class Truc(PrimaryView):
          def f(self, arg1):
              super(Truc, self).f(arg1)
