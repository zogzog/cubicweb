.. _controllers:

Controllers
-----------

Overview
++++++++

Controllers are responsible for taking action upon user requests
(loosely following the terminology of the MVC meta pattern).

The following controllers are provided out-of-the box in CubicWeb. We
list them by category.

`Browsing`:

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

`Edition`:

* the Edit controller (see :ref:`edit_controller`) handles CRUD
  operations in response to a form being submitted; it works in close
  association with the Forms, to which it delegates some of the work

* the Form validator controller (web/views/basecontrollers.py)
  provides form validation from Ajax context, using the Edit
  controller, to implement the classic form handling loop (user edits,
  hits 'submit/apply', validation occurs server-side by way of the
  Form validator controller, and the UI is decorated with failure
  information, either global or per-field , until it is valid)

`Other`:

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


.. _edit_controller:

The `edit controller`
+++++++++++++++++++++

It can be found in (:mod:`cubicweb.web.views.editcontroller`).

Editing control
~~~~~~~~~~~~~~~~

Re-requisites: the parameters related to entities to edit are
specified as follows ::

  <field name>:<entity eid>

where entity eid could be a letter in case of an entity to create. We
name those parameters as *qualified*.

1. Retrieval of entities to edit by looking for the forms parameters
   starting by `eid:` and also having a parameter `__type` associated
   (also *qualified* by eid)

2. For all the attributes and the relations of an entity to edit:

   1. search for a parameter `edits-<relation name>` or `edito-<relation name>`
      qualified in the case of a relation where the entity is object
   2. if found, the value returned is considered as the initial value
      for this relaiton and we then look for the new value(s)  in the parameter
      <relation name> (qualified)
   3. if the value returned is different from the initial value, an database update
      request is done

3. For each entity to edit:

   1. if a qualified parameter `__linkto` is specified, its value has to be
      a string (or a list of string) such as: ::

        <relation type>:<eids>:<target>

      where <target> is either `subject` or `object` and each eid could be
      separated from the others by a `_`. Target specifies if the *edited entity*
      is subject or object of the relation and each relation specified will
      be inserted.

    2. if a qualified parameter `__clone_eid` is specified for an entity, the
       relations of the specified entity passed as value of this parameter are
       copied on the edited entity.

    3. if a qualified parameter `__delete` is specified, its value must be
       a string or a list of string such as follows: ::

          <ssubjects eids>:<relation type>:<objects eids>

       where each eid subject or object can be seperated from the other
       by `_`. Each relation specified will be deleted.

    4. if a qualified parameter `__insert` is specified, its value should
       follow the same pattern as `__delete`, but each relation specified is
       inserted.

4. If the parameters `__insert` and/or `__delete` are found not qualified,
   they are interpreted as explained above (independantly from the number
   of entities edited).

5. If no entity is edited but the form contains the parameters `__linkto`
   and `eid`, this one is interpreted by using the value specified for `eid`
   to designate the entity on which to add the relations.


.. note::

   * If the parameter `__action_delete` is found, all the entities specified
     as to be edited will be deleted.

   * If the parameter `__action_cancel` is found, no action is completed.

   * If the parameter `__action_apply` is found, the editing is
     applied normally but the redirection is done on the form (see
     :ref:`RedirectionControl`).

   * The parameter `__method` is also supported as for the main template

   * If no entity is found to be edited and if there is no parameter
     `__action_delete`, `__action_cancel`, `__linkto`, `__delete` or
     `__insert`, an error is raised.

   * Using the parameter `__message` in the form will allow to use its value
     as a message to provide the user once the editing is completed.


.. _RedirectionControl:

Redirection control
~~~~~~~~~~~~~~~~~~~
Once editing is completed, there is still an issue left: where should we go
now? If nothing is specified, the controller will do his job but it does not
mean we will be happy with the result. We can control that by using the
following parameters:

* `__redirectpath`: path of the URL (relative to the root URL of the site,
  no form parameters

* `__redirectparams`: forms parameters to add to the path

* `__redirectrql`: redirection RQL request

* `__redirectvid`: redirection view identifier

* `__errorurl`: initial form URL, used for redirecting in case a validation
  error is raised during editing. If this one is not specified, an error page
  is displayed instead of going back to the form (which is, if necessary,
  responsible for displaying the errors)

* `__form_id`: initial view form identifier, used if `__action_apply` is
  found

In general we use either `__redirectpath` and `__redirectparams` or
`__redirectrql` and `__redirectvid`.

