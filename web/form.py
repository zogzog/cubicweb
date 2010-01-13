"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from warnings import warn

from logilab.common.decorators import iclassmethod
from logilab.common.deprecation import deprecated

from cubicweb.appobject import AppObject
from cubicweb.view import NOINDEX, NOFOLLOW
from cubicweb import tags
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


###############################################################################

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

    parent_form = None
    force_session_key = None

    def __init__(self, req, rset, **kwargs):
        super(Form, self).__init__(req, rset=rset, **kwargs)
        self.restore_previous_post(self.session_key())

    @property
    def root_form(self):
        """return the root form"""
        if self.parent_form is None:
            return self
        return self.parent_form.root_form

    @property
    def form_valerror(self):
        """the validation error exception if any"""
        if self.parent_form is None:
            return self._form_valerror
        return self.parent_form.form_valerror

    @property
    def form_previous_values(self):
        """previously posted values (on validation error)"""
        if self.parent_form is None:
            return self._form_previous_values
        return self.parent_form.form_previous_values

    @iclassmethod
    def _fieldsattr(cls_or_self):
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        return fields

    @iclassmethod
    def field_by_name(cls_or_self, name, role=None):
        """return field with the given name and role.
        Raise FieldNotFound if the field can't be found.
        """
        for field in cls_or_self._fieldsattr():
            if field.name == name and field.role == role:
                return field
        raise FieldNotFound(name)

    @iclassmethod
    def fields_by_name(cls_or_self, name, role=None):
        """return a list of fields with the given name and role"""
        return [field for field in cls_or_self._fieldsattr()
                if field.name == name and field.role == role]

    @iclassmethod
    def remove_field(cls_or_self, field):
        """remove a field from form class or instance"""
        cls_or_self._fieldsattr().remove(field)

    @iclassmethod
    def append_field(cls_or_self, field):
        """append a field to form class or instance"""
        cls_or_self._fieldsattr().append(field)

    @iclassmethod
    def insert_field_before(cls_or_self, new_field, name, role='subject'):
        field = cls_or_self.field_by_name(name, role)
        fields = cls_or_self._fieldsattr()
        fields.insert(fields.index(field), new_field)

    @iclassmethod
    def insert_field_after(cls_or_self, new_field, name, role='subject'):
        field = cls_or_self.field_by_name(name, role)
        fields = cls_or_self._fieldsattr()
        fields.insert(fields.index(field)+1, new_field)

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        if self.force_session_key is None:
            return '%s#%s' % (self._cw.url(), self.domid)
        return self.force_session_key

    def restore_previous_post(self, sessionkey):
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        forminfo = self._cw.get_session_data(sessionkey, pop=True)
        if forminfo:
            self._form_previous_values = forminfo['values']
            self._form_valerror = forminfo['error']
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
            self._form_previous_values = {}
            self._form_valerror = None

    def field_error(self, field):
        """return field's error if specified in current validation exception"""
        if self.form_valerror:
            if field.eidparam and self.edited_entity.eid != self.form_valerror.eid:
                return None
            try:
                return self.form_valerror.errors.pop(field.role_name())
            except KeyError:
                if field.role and field.name in self.form_valerror:
                    warn('%s: errors key of attribute/relation should be suffixed by "-<role>"'
                         % self.form_valerror.__class__, DeprecationWarning)
                    return self.form_valerror.errors.pop(field.name)
        return None

    def remaining_errors(self):
        return sorted(self.form_valerror.errors.items())

    @deprecated('[3.6] use form.field_error and/or new renderer.render_error method')
    def form_field_error(self, field):
        """return validation error for widget's field, if any"""
        err = self.field_error(field)
        if err:
            return u'<span class="error">%s</span>' % err
        return u''

