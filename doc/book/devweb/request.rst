The `Request` class (`cubicweb.web.request`)
--------------------------------------------

Overview
````````

A request instance is created when an HTTP request is sent to the web
server.  It contains informations such as form parameters,
authenticated user, etc. It is a very prevalent object and is used
throughout all of the framework and applications, as you'll access to
almost every resources through it.

**A request represents a user query, either through HTTP or not (we
also talk about RQL queries on the server side for example).**

Here is a non-exhaustive list of attributes and methods available on
request objects (grouped by category):

* `Browser control`:

  * `ie_browser`: tells if the browser belong to the Internet Explorer
    family

* `User and identification`:

  * `user`, instance of `cubicweb.entities.authobjs.CWUser` corresponding to the
    authenticated user

* `Session data handling`

  * `session.data` is the dictionary of the session data; it can be
    manipulated like an ordinary Python dictionary

* `Edition` (utilities for edition control):

  * `cancel_edition`: resets error url and cleans up pending operations
  * `create_entity`: utility to create an entity (from an etype,
    attributes and relation values)
  * `datadir_url`: returns the url to the merged external resources
    (|cubicweb|'s `web/data` directory plus all `data` directories of
    used cubes)
  * `edited_eids`: returns the list of eids of entities that are
    edited under the current http request
  * `eid_rset(eid)`: utility which returns a result set from an eid
  * `entity_from_eid(eid)`: returns an entity instance from the given eid
  * `encoding`: returns the encoding of the current HTTP request
  * `ensure_ro_rql(rql)`: ensure some rql query is a data request
  * etype_rset
  * `form`, dictionary containing the values of a web form
  * `encoding`, character encoding to use in the response

* `HTTP`

  * `authmode`: returns a string describing the authentication mode
    (http, cookie, ...)
  * `lang`: returns the user agents/browser's language as carried by
    the http request
  * `demote_to_html()`: in the context of an XHTML compliant browser,
    this will force emission of the response as an HTML document
    (using the http content negociation)

*  `Cookies handling`

  * `get_cookie()`, returns a dictionary containing the value of the header
    HTTP 'Cookie'
  * `set_cookie(cookie, key, maxage=300)`, adds a header HTTP `Set-Cookie`,
    with a minimal 5 minutes length of duration by default (`maxage` = None
    returns a *session* cookie which will expire when the user closes the browser
    window)
  * `remove_cookie(cookie, key)`, forces a value to expire

* `URL handling`

  * `build_url(__vid, *args, **kwargs)`: return an absolute URL using
    params dictionary key/values as URL parameters. Values are
    automatically URL quoted, and the publishing method to use may be
    specified or will be guessed.
  * `build_url_params(**kwargs)`: returns a properly prepared (quoted,
    separators, ...) string from the given parameters
  * `url()`, returns the full URL of the HTTP request
  * `base_url()`, returns the root URL of the web application
  * `relative_path()`, returns the relative path of the request

* `Web resource (.css, .js files, etc.) handling`:

  * `add_css(cssfiles)`: adds the given list of css resources to the current
    html headers
  * `add_js(jsfiles)`: adds the given list of javascript resources to the
    current html headers
  * `add_onload(jscode)`: inject the given jscode fragment (a unicode
    string) into the current html headers, wrapped inside a
    document.ready(...) or another ajax-friendly one-time trigger event
  * `add_header(header, values)`: adds the header/value pair to the
    current html headers
  * `status_out`: control the HTTP status of the response

* `And more...`

  * `set_content_type(content_type, filename=None)`, adds the header HTTP
    'Content-Type'
  * `get_header(header)`, returns the value associated to an arbitrary header
    of the HTTP request
  * `set_header(header, value)`, adds an arbitrary header in the response
  * `execute(*args, **kwargs)`, executes an RQL query and return the result set
  * `property_value(key)`, properties management (`CWProperty`)
  * dictionary `data` to store data to share informations between components
    *while a request is executed*

Please note that this class is abstract and that a concrete implementation
will be provided by the *frontend* web used. For the views or others that are
executed on the server side, most of the interface of `Request` is defined in
the session associated to the client.

API
```

The elements we gave in overview for above are built in three layers,
from ``cubicweb.req.RequestSessionBase``, ``cubicweb.repoapi.Connection`` and
``cubicweb.web.ConnectionCubicWebRequestBase``.

.. autoclass:: cubicweb.req.RequestSessionBase
   :members:

.. autoclass:: cubicweb.repoapi.Connection
   :members:

.. autoclass:: cubicweb.web.request.ConnectionCubicWebRequestBase
   :members:
