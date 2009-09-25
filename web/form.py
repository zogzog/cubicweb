"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.appobject import AppObject
from cubicweb.view import NOINDEX, NOFOLLOW
from cubicweb.common import tags
from cubicweb.web import stdmsgs, httpcache, formfields


class FormViewMixIn(object):
    """abstract form view mix-in"""
    category = 'form'
    http_cache_manager = httpcache.NoHTTPCacheManager
    add_to_breadcrumbs = False

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default forms are neither indexed nor followed
        """
        return [NOINDEX, NOFOLLOW]

    def linkable(self):
        """override since forms are usually linked by an action,
        so we don't want them to be listed by appli.possible_views
        """
        return False


class metafieldsform(type):
    """metaclass for FieldsForm to retrieve fields defined as class attributes
    and put them into a single ordered list: '_fields_'.
    """
    def __new__(mcs, name, bases, classdict):
        allfields = []
        for base in bases:
            if hasattr(base, '_fields_'):
                allfields += base._fields_
        clsfields = (item for item in classdict.items()
                     if isinstance(item[1], formfields.Field))
        for fieldname, field in sorted(clsfields, key=lambda x: x[1].creation_rank):
            if not field.name:
                field.set_name(fieldname)
            allfields.append(field)
        classdict['_fields_'] = allfields
        return super(metafieldsform, mcs).__new__(mcs, name, bases, classdict)


class FieldNotFound(Exception):
    """raised by field_by_name when a field with the given name has not been
    found
    """

class Form(AppObject):
    __metaclass__ = metafieldsform
    __registry__ = 'forms'

    def __init__(self, req, rset, **kwargs):
        super(Form, self).__init__(req, rset=rset, **kwargs)
        self.restore_previous_post(self.session_key())

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        return '%s#%s' % (self._cw.url(), self.domid)

    def restore_previous_post(self, sessionkey):
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        forminfo = self._cw.get_session_data(sessionkey, pop=True)
        if forminfo:
            # XXX remove req.data assigment once cw.web.widget is killed
            self._cw.data['formvalues'] = self.form_previous_values = forminfo['values']
            self._cw.data['formerrors'] = self.form_valerror = forminfo['errors']
            self._cw.data['displayederrors'] = self.form_displayed_errors = set()
            # if some validation error occured on entity creation, we have to
            # get the original variable name from its attributed eid
            foreid = self.form_valerror.entity
            for var, eid in forminfo['eidmap'].items():
                if foreid == eid:
                    self.form_valerror.eid = var
                    break
            else:
                self.form_valerror.eid = foreid
        else:
            self.form_previous_values = {}
            self.form_valerror = None
