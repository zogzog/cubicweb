"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.selectors import implements
from cubicweb.sobjects.notification import StatusChangeMixIn, NotificationView

class UserStatusChangeView(StatusChangeMixIn, NotificationView):
    __select__ = NotificationView.__select__ & implements('CWUser')
