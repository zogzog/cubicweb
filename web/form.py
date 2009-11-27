"""abstract form classes for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import iclassmethod

from cubicweb.appobject import AppObject
from cubicweb.view import NOINDEX, NOFOLLOW
from cubicweb.common import tags
from cubicweb.web import stdmsgs, httpcache, formfields


class FormViewMixIn(object):
    """abstract form view mix-in"""
    category = 'form'
    controller = 'edit'
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


# XXX should disappear
class FormMixIn(object):
    """abstract form mix-in
    XXX: you should inherit from this FIRST (obscure pb with super call)
    """
    force_session_key = None

    def session_key(self):
        """return the key that may be used to store / retreive data about a
        previous post which failed because of a validation error
        """
        if self.force_session_key is None:
            return '%s#%s' % (self.req.url(), self.domid)
        return self.force_session_key

    def restore_previous_post(self, sessionkey):
        # get validation session data which may have been previously set.
        # deleting validation errors here breaks form reloading (errors are
        # no more available), they have to be deleted by application's publish
        # method on successful commit
        forminfo = self.req.get_session_data(sessionkey, pop=True)
        if forminfo:
            # XXX remove req.data assigment once cw.web.widget is killed
            self.req.data['formvalues'] = self._form_previous_values = forminfo['values']
            self.req.data['formerrors'] = self._form_valerror = forminfo['errors']
            self.req.data['displayederrors'] = self.form_displayed_errors = set()
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

    @property
    def form_previous_values(self):
        if self.parent_form is None:
            return self._form_previous_values
        return self.parent_form.form_previous_values

    @property
    def form_valerror(self):
        if self.parent_form is None:
            return self._form_valerror
        return self.parent_form.form_valerror

    # XXX deprecated with new form system. Should disappear

    domid = 'entityForm'
    category = 'form'
    controller = 'edit'
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


    def button(self, label, klass='validateButton', tabindex=None, **kwargs):
        if tabindex is None:
            tabindex = self.req.next_tabindex()
        return tags.input(value=label, klass=klass, **kwargs)

    def action_button(self, label, onclick=None, __action=None, **kwargs):
        if onclick is None:
            onclick = "postForm('__action_%s', \'%s\', \'%s\')" % (
                __action, label, self.domid)
        return self.button(label, onclick=onclick, **kwargs)

    def button_ok(self, label=None, type='submit', name='defaultsubmit',
                  **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_OK).capitalize()
        return self.button(label, name=name, type=type, **kwargs)

    def button_apply(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_APPLY).capitalize()
        return self.action_button(label, __action='apply', type=type, **kwargs)

    def button_delete(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_DELETE).capitalize()
        return self.action_button(label, __action='delete', type=type, **kwargs)

    def button_cancel(self, label=None, type='button', **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.action_button(label, __action='cancel', type=type, **kwargs)

    def button_reset(self, label=None, type='reset', name='__action_cancel',
                     **kwargs):
        label = self.req._(label or stdmsgs.BUTTON_CANCEL).capitalize()
        return self.button(label, type=type, **kwargs)

    def need_multipart(self, entity, categories=('primary', 'secondary')):
        """return a boolean indicating if form's enctype should be multipart
        """
        for rschema, _, x in entity.relations_by_category(categories):
            if entity.get_widget(rschema, x).need_multipart:
                return True
        # let's find if any of our inlined entities needs multipart
        for rschema, targettypes, x in entity.relations_by_category('inlineview'):
            assert len(targettypes) == 1, \
                   "I'm not able to deal with several targets and inlineview"
            ttype = targettypes[0]
            inlined_entity = self.vreg.etype_class(ttype)(self.req, None, None)
            for irschema, _, x in inlined_entity.relations_by_category(categories):
                if inlined_entity.get_widget(irschema, x).need_multipart:
                    return True
        return False

    def error_message(self):
        """return formatted error message

        This method should be called once inlined field errors has been consumed
        """
        errex = self.req.data.get('formerrors') or self.form_valerror
        # get extra errors
        if errex is not None:
            errormsg = self.req._('please correct the following errors:')
            displayed = self.req.data.get('displayederrors') or self.form_displayed_errors
            errors = sorted((field, err) for field, err in errex.errors.items()
                            if not field in displayed)
            if errors:
                if len(errors) > 1:
                    templstr = '<li>%s</li>\n'
                else:
                    templstr = '&#160;%s\n'
                for field, err in errors:
                    if field is None:
                        errormsg += templstr % err
                    else:
                        errormsg += templstr % '%s: %s' % (self.req._(field), err)
                if len(errors) > 1:
                    errormsg = '<ul>%s</ul>' % errormsg
            return u'<div class="errorMessage">%s</div>' % errormsg
        return u''


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

class Form(FormMixIn, AppObject):
    __metaclass__ = metafieldsform
    __registry__ = 'forms'

    parent_form = None

    @property
    def root_form(self):
        """return the root form"""
        if self.parent_form is None:
            return self
        return self.parent_form.root_form

    @iclassmethod
    def _fieldsattr(cls_or_self):
        if isinstance(cls_or_self, type):
            fields = cls_or_self._fields_
        else:
            fields = cls_or_self.fields
        return fields

    @iclassmethod
    def field_by_name(cls_or_self, name, role='subject'):
        """return field with the given name and role.
        Raise FieldNotFound if the field can't be found.
        """
        for field in cls_or_self._fieldsattr():
            if field.name == name and field.role == role:
                return field
        raise FieldNotFound(name)

    @iclassmethod
    def fields_by_name(cls_or_self, name, role='subject'):
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
