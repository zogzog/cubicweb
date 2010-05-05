.. _edit_controller:

The `edit controller`
---------------------

It can be found in (:mod:`cubicweb.web.views.editcontroller`). This
controller processes data received from an html form to create or
update entities.

Edition handling
~~~~~~~~~~~~~~~~

The parameters related to entities to edit are specified as follows
(first seen in :ref:`attributes_section`)::

  <rtype-role>:<entity eid>

where entity eid could be a letter in case of an entity to create. We
name those parameters as *qualified*.

* Retrieval of entities to edit is done by using the forms parameters
  `eid` and `__type`

* For all the attributes and the relations of an entity to edit
  (attributes and relations are handled a bit differently but these
  details are not much relevant here) :

   * using the ``rtype``, ``role`` and ``__type`` information, fetch
     an appropriate field instance

   * check if the field has been modified (if not, proceed to the next
     relation)

   * build an rql expression to update the entity

At the end, all rql expressions are executed.

* For each entity to edit:

   * if a qualified parameter `__linkto` is specified, its value has
     to be a string (or a list of strings) such as: ::

        <relation type>:<eids>:<target>

     where <target> is either `subject` or `object` and each eid could
     be separated from the others by a `_`. Target specifies if the
     *edited entity* is subject or object of the relation and each
     relation specified will be inserted.

    * if a qualified parameter `__clone_eid` is specified for an entity, the
      relations of the specified entity passed as value of this parameter are
      copied on the edited entity.

    * if a qualified parameter `__delete` is specified, its value must be
      a string or a list of string such as follows: ::

          <subjects eids>:<relation type>:<objects eids>

      where each eid subject or object can be seperated from the other
      by `_`. Each specified relation will be deleted.


* If no entity is edited but the form contains the parameters `__linkto`
  and `eid`, this one is interpreted by using the value specified for `eid`
  to designate the entity on which to add the relations.

.. note::

   * if the parameter `__action_delete` is found, all the entities specified
     as to be edited will be deleted.

   * if the parameter `__action_cancel` is found, no action is completed.

   * if the parameter `__action_apply` is found, the editing is
     applied normally but the redirection is done on the form (see
     :ref:`RedirectionControl`).

   * if no entity is found to be edited and if there is no parameter
     `__action_delete`, `__action_cancel`, `__linkto`, `__delete` or
     `__insert`, an error is raised.

   * using the parameter `__message` in the form will allow to use its value
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
