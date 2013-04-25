.. -*- coding: utf-8 -*-

Notifications management
========================

CubicWeb provides a machinery to ease notifications handling. To use it for a
notification:

* write a view inheriting from
  :class:`~cubicweb.sobjects.notification.NotificationView`.  The usual view api
  is used to generated the email (plain text) content, and additional
  :meth:`~cubicweb.sobjects.notification.NotificationView.subject` and
  :meth:`~cubicweb.sobjects.notification.NotificationView.recipients` methods
  are used to build the email's subject and
  recipients. :class:`NotificationView` provides default implementation for both
  methods.

* write a hook for event that should trigger this notification, select the view
  (without rendering it), and give it to
  :func:`cubicweb.hooks.notification.notify_on_commit` so that the notification
  will be sent if the transaction succeed.


.. XXX explain recipient finder and provide example

API details
~~~~~~~~~~~
.. autoclass:: cubicweb.sobjects.notification.NotificationView
.. autofunction:: cubicweb.hooks.notification.notify_on_commit
