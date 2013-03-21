.. _ajax:

Ajax
----

CubicWeb provides a few helpers to facilitate *javascript <-> python* communications.

You can, for instance, register some python functions that will become
callable from javascript through ajax calls. All the ajax URLs are handled
by the :class:`cubicweb.web.views.ajaxcontroller.AjaxController` controller.

.. automodule:: cubicweb.web.views.ajaxcontroller
