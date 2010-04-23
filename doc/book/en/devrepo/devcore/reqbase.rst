Request and ResultSet methods
-----------------------------

Those are methods you'll find on both request objects and on
repository session.

Request methods
~~~~~~~~~~~~~~~

`URL handling`:

* `build_url(*args, **kwargs)`, returns an absolute URL based on the
  given arguments. The *controller* supposed to handle the response,
  can be specified through the first positional parameter (the
  connection is theoretically done automatically :).

`Data formatting`:

* `format_date(date, date_format=None, time=False)` returns a string for a
  date time according to instance's configuration

* `format_time(time)` returns a string for a date time according to
  instance's configuration

`And more...`:

* `tal_render(template, variables)`, renders a precompiled page template with
  variables in the given dictionary as context


Result set methods
~~~~~~~~~~~~~~~~~~

* `get_entity(row, col)`, returns the entity corresponding to the data position
  in the *result set*

* `complete_entity(row, col, skip_bytes=True)`, is equivalent to `get_entity` but
  also call the method `complete()` on the entity before returning it


