Controllers
-----------

Overview
++++++++

Controllers are responsible for taking action upon user requests
(loosely following the terminology of the MVC meta pattern).

The following controllers are provided out-of-the box in CubicWeb. We
list them by category.

Browsing:

* the View controller (web/views/basecontrollers.py) is associated
  with most browsing actions within a CubicWeb application: it always
  instantiates a `main template` and lets the ResultSet/Views dispatch
  system build up the whole content; it handles ObjectNotFound and
  NoSelectableObject errors that may bubble up to its entry point, in
  an end-user-friendly way (but other programming errors will slip
  through)

* the JSon controller (web/views/basecontrollers.py) provides services
  for Ajax calls, typically using JSON as a serialization format for
  input, and sometimes using either JSON or XML for output; 

* the Login/Logout controllers (web/views/basecontrollers.py) make
  effective user login or logout requests

Edition:

* the Edit controller (web/views/editcontroller.py) handles CRUD
  operations in response to a form being submitted; it works in close
  association with the Forms, to which it delegates some of the work

* the Form validator controller (web/views/basecontrollers.py)
  provides form validation from Ajax context, using the Edit
  controller, to implement the classic form handling loop (user edits,
  hits 'submit/apply', validation occurs server-side by way of the
  Form validator controller, and the UI is decorated with failure
  information, either global or per-field , until it is valid)

Other:

* the SendMail controller (web/views/basecontrollers.py) is reponsible
  for outgoing email notifications

* the MailBugReport controller (web/views/basecontrollers.py) allows
  to quickly have a `repotbug` feature in one's application

Registration
++++++++++++

All controllers (should) live in the 'controllers' namespace within
the global registry.

API
+++

Most API details should be resolved by source code inspection, as the
various controllers have differing goals.

`web/controller.py` contains the top-level abstract Controller class and
its (NotImplemented) entry point `publish(rset=None)` method.

A handful of helpers are also provided there:

* process_rql builds a result set from an rql query typically issued
  from the browser (and available through _cw.form['rql'])

* validate_cache will force cache validation handling with respect to
  the HTTP Cache directives (that were typically originally issued
  from a previous server -> client response); concrete Controller
  implementations dealing with HTTP (thus, for instance, not the
  SendMail controller) may very well call this in their publication
  process.



