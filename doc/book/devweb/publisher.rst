.. _publisher:

Publisher
---------

What happens when an HTTP request is issued ?

The story begins with the ``CubicWebPublisher.main_publish``
method. We do not get upper in the bootstrap process because it is
dependant on the used HTTP library.

What main_publish does:

* get a controller id and a result set from the path (this is actually
  delegated to the `urlpublisher` component)

* the controller is then selected (if not, this is considered an
  authorization failure and signaled as such) and called

* then either a proper result is returned, in which case the
  request/connection object issues a ``commit`` and returns the result

* or error handling must happen:

  * ``ValidationErrors`` pop up there and may lead to a redirect to a
    previously arranged url or standard error handling applies
  * an HTTP 500 error (`Internal Server Error`) is issued


Now, let's turn to the controller. There are many of them in
:mod:`cubicweb.web.views.basecontrollers`. We can just follow the
default `view` controller that is selected on a `view` path. See the
:ref:`controllers` chapter for more information on controllers.

The `View` controller's entry point is the `publish` method. It does
the following:

* compute the `main` view to be applied, using either the given result
  set or building one from a user provided rql string (`rql` and `vid`
  can be forced from the url GET parameters), that is:

    * compute the `vid` using the result set and the schema (see
      `cubicweb.web.views.vid_from_rset`)
    * handle all error cases that could happen in this phase

* do some cache management chores

* select a main template (typically `TheMainTemplate`, see chapter
  :ref:`templates`)

* call it with the result set and the computed view.

What happens next actually depends on the template and the view, but
in general this is the rendering phase.


CubicWebPublisher API
`````````````````````

.. autoclass:: cubicweb.web.application.CubicWebPublisher
   :members:
