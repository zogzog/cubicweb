

The `Request` class (`cubicweb.web`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A._cwuest instance is created when an HTTP._cwuest is sent to the web server.
It contains informations such as form parameters, user authenticated, etc.

**Globally, a._cwuest represents a user query, either through HTTP or not
(we also talk about RQL queries on the server side for example).**

An instance of `Request` has the following attributes:

* `user`, instance of `cubicweb.common.utils.User` corresponding to the authenticated
  user
* `form`, dictionary containing the values of a web form
* `encoding`, character encoding to use in the response

But also:

:Session data handling:
  * `session_data()`, returns a dictionary containing all the session data
  * `get_session_data(key, default=None)`, returns a value associated to the given
    key or the value `default` if the key is not defined
  * `set_session_data(key, value)`, assign a value to a key
  * `del_session_data(key)`,  suppress the value associated to a key


:Cookies handling:
  * `get_cookie()`, returns a dictionary containing the value of the header
    HTTP 'Cookie'
  * `set_cookie(cookie, key, maxage=300)`, adds a header HTTP `Set-Cookie`,
    with a minimal 5 minutes length of duration by default (`maxage` = None
    returns a *session* cookie which will expire when the user closes the browser
    window)
  * `remove_cookie(cookie, key)`, forces a value to expire

:URL handling:
  * `url()`, returns the full URL of the HTTP._cwuest
  * `base_url()`, returns the root URL of the web application
  * `relative_path()`, returns the relative path of the._cwuest

:And more...:
  * `set_content_type(content_type, filename=None)`, adds the header HTTP
    'Content-Type'
  * `get_header(header)`, returns the value associated to an arbitrary header
    of the HTTP._cwuest
  * `set_header(header, value)`, adds an arbitrary header in the response
  * `cursor()` returns a RQL cursor on the session
  * `execute(*args, **kwargs)`, shortcut to ``.cursor().execute()``
  * `property_value(key)`, properties management (`CWProperty`)
  * dictionary `data` to store data to share informations between components
    *while a._cwuest is executed*

Please note that this class is abstract and that a concrete implementation
will be provided by the *frontend* web used (in particular *twisted* as of
today). For the views or others that are executed on the server side,
most of the interface of `Request` is defined in the session associated
to the client.
