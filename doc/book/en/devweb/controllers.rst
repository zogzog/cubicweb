.. _controllers:

Controllers
-----------

Overview
++++++++

Controllers are responsible for taking action upon user requests
(loosely following the terminology of the MVC meta pattern).

The following controllers are provided out-of-the box in CubicWeb. We
list them by category. They are all defined in
(:mod:`cubicweb.web.views.basecontrollers`).

`Browsing`:

* the View controller is associated with most browsing actions within a
  CubicWeb application: it always instantiates a
  :ref:`the_main_template_layout` and lets the ResultSet/Views dispatch system
  build up the whole content; it handles :exc:`ObjectNotFound` and
  :exc:`NoSelectableObject` errors that may bubble up to its entry point, in an
  end-user-friendly way (but other programming errors will slip through)

* the JSonpController is a wrapper around the ``ViewController`` that
  provides jsonp_ services. Padding can be specified with the
  ``callback`` request parameter. Only *jsonexport* / *ejsonexport*
  views can be used. If another ``vid`` is specified, it will be
  ignored and replaced by *jsonexport*. Request is anonymized
  to avoid returning sensitive data and reduce the risks of CSRF attacks;

* the Login/Logout controllers make effective user login or logout
  requests


.. _jsonp: http://en.wikipedia.org/wiki/JSONP

`Edition`:

* the Edit controller (see :ref:`edit_controller`) handles CRUD
  operations in response to a form being submitted; it works in close
  association with the Forms, to which it delegates some of the work

* the ``Form validator controller`` provides form validation from Ajax
  context, using the Edit controller, to implement the classic form
  handling loop (user edits, hits `submit/apply`, validation occurs
  server-side by way of the Form validator controller, and the UI is
  decorated with failure information, either global or per-field ,
  until it is valid)

`Other`:

* the ``SendMail controller`` (web/views/basecontrollers.py) is reponsible
  for outgoing email notifications

* the MailBugReport controller (web/views/basecontrollers.py) allows
  to quickly have a `reportbug` feature in one's application

* the :class:`cubicweb.web.views.ajaxcontroller.AjaxController`
  (:mod:`cubicweb.web.views.ajaxcontroller`) provides
  services for Ajax calls, typically using JSON as a serialization format
  for input, and sometimes using either JSON or XML for output. See
  :ref:`ajax` chapter for more information.


Registration
++++++++++++

All controllers (should) live in the 'controllers' namespace within
the global registry.

Concrete controllers
++++++++++++++++++++

Most API details should be resolved by source code inspection, as the
various controllers have differing goals. See for instance the
:ref:`edit_controller` chapter.

:mod:`cubicweb.web.controller` contains the top-level abstract
Controller class and its unimplemented entry point
`publish(rset=None)` method.

A handful of helpers are also provided there:

* process_rql builds a result set from an rql query typically issued
  from the browser (and available through _cw.form['rql'])

* validate_cache will force cache validation handling with respect to
  the HTTP Cache directives (that were typically originally issued
  from a previous server -> client response); concrete Controller
  implementations dealing with HTTP (thus, for instance, not the
  SendMail controller) may very well call this in their publication
  process.
