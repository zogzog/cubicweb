from cubicweb.selectors import implements
from cubicweb.sobjects.notification import StatusChangeMixIn, NotificationView

class UserStatusChangeView(StatusChangeMixIn, NotificationView):
    __select__ = NotificationView.__select__ & implements('CWUser')
