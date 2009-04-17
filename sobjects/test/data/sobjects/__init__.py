from cubicweb.sobjects.notification import StatusChangeMixIn, NotificationView

class UserStatusChangeView(StatusChangeMixIn, NotificationView):
    accepts = ('CWUser',)
    
    
