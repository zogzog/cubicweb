XXX todo:
* configure members for doc generated for appojbect class,
* configure module's member into the module
* put doc below somewhere else

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
