.. _ajax:

Ajax
----

.. warning::

    This approach is deprecated in favor of using
    `cwclientlibjs <https://www.npmjs.com/package/@logilab/cwclientlibjs>`_.
    If your use react for your UI, try the react components from the
    `cwelements <https://www.npmjs.com/package/@logilab/cwelements>`_ library.
    The documentation is kept here as reference.

    For historical reference of what Ajax is and used to be, one can read the
    `wikipedia article about Ajax <https://en.wikipedia.org/wiki/Ajax_(programming)>`_.

CubicWeb provides a few helpers to facilitate *javascript <-> python* communications.

You can, for instance, register some python functions that will become
callable from javascript through ajax calls. All the ajax URLs are handled
by the :class:`cubicweb.web.views.ajaxcontroller.AjaxController` controller.

.. automodule:: cubicweb.web.views.ajaxcontroller
