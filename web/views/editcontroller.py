# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""The edit controller, automatically handling entity form submitting"""

__docformat__ = "restructuredtext en"

from warnings import warn

from rql.utils import rqlvar_maker

from logilab.common.textutils import splitstrip

from cubicweb import Binary, ValidationError, typed_eid
from cubicweb.view import EntityAdapter, implements_adapter_compat
from cubicweb.selectors import is_instance
from cubicweb.web import (INTERNAL_FIELD_VALUE, RequestError, NothingToEdit,
                          ProcessFormError)
from cubicweb.web.views import basecontrollers, autoform


class IEditControlAdapter(EntityAdapter):
    __regid__ = 'IEditControl'
    __select__ = is_instance('Any')

    @implements_adapter_compat('IEditControl')
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        parent = self.entity.cw_adapt_to('IBreadCrumbs').parent_entity()
        if parent is not None:
            return parent.rest_path(), {}
        return str(self.entity.e_schema).lower(), {}

    @implements_adapter_compat('IEditControl')
    def pre_web_edit(self):
        """callback called by the web editcontroller when an entity will be
        created/modified, to let a chance to do some entity specific stuff.

        Do nothing by default.
        """
        pass


def valerror_eid(eid):
    try:
        return typed_eid(eid)
    except (ValueError, TypeError):
        return eid

class RqlQuery(object):
    def __init__(self):
        self.edited = []
        self.restrictions = []
        self.kwargs = {}

    def insert_query(self, etype):
        if self.edited:
            rql = 'INSERT %s X: %s' % (etype, ','.join(self.edited))
        else:
            rql = 'INSERT %s X' % etype
        if self.restrictions:
            rql += ' WHERE %s' % ','.join(self.restrictions)
        return rql

    def update_query(self, eid):
        varmaker = rqlvar_maker()
        var = varmaker.next()
        while var in self.kwargs:
            var = varmaker.next()
        rql = 'SET %s WHERE X eid %%(%s)s' % (','.join(self.edited), var)
        if self.restrictions:
            rql += ', %s' % ','.join(self.restrictions)
        self.kwargs[var] = eid
        return rql


class EditController(basecontrollers.ViewController):
    __regid__ = 'edit'

    def publish(self, rset=None):
        """edit / create / copy / delete entity / relations"""
        for key in self._cw.form:
            # There should be 0 or 1 action
            if key.startswith('__action_'):
                cbname = key[1:]
                try:
                    callback = getattr(self, cbname)
                except AttributeError:
                    raise RequestError(self._cw._('invalid action %r' % key))
                else:
                    return callback()
        self._default_publish()
        self.reset()

    def _default_publish(self):
        req = self._cw
        self.errors = []
        self.relations_rql = []
        form = req.form
        # so we're able to know the main entity from the repository side
        if '__maineid' in form:
            req.set_shared_data('__maineid', form['__maineid'], txdata=True)
        # no specific action, generic edition
        self._to_create = req.data['eidmap'] = {}
        self._pending_fields = req.data['pendingfields'] = set()
        try:
            for eid in req.edited_eids():
                # __type and eid
                formparams = req.extract_entity_params(eid, minparams=2)
                eid = self.edit_entity(formparams)
        except (RequestError, NothingToEdit), ex:
            if '__linkto' in req.form and 'eid' in req.form:
                self.execute_linkto()
            elif not ('__delete' in req.form or '__insert' in req.form):
                raise ValidationError(None, {None: unicode(ex)})
        # handle relations in newly created entities
        if self._pending_fields:
            for form, field in self._pending_fields:
                self.handle_formfield(form, field)
        # execute rql to set all relations
        for querydef in self.relations_rql:
            self._cw.execute(*querydef)
        # XXX this processes *all* pending operations of *all* entities
        if req.form.has_key('__delete'):
            todelete = req.list_form_param('__delete', req.form, pop=True)
            if todelete:
                autoform.delete_relations(self._cw, todelete)
        if req.form.has_key('__insert'):
            warn('[3.6] stop using __insert, support will be removed',
                 DeprecationWarning)
            toinsert = req.list_form_param('__insert', req.form, pop=True)
            if toinsert:
                autoform.insert_relations(self._cw, toinsert)
        self._cw.remove_pending_operations()
        if self.errors:
            errors = dict((f.name, unicode(ex)) for f, ex in self.errors)
            raise ValidationError(valerror_eid(form.get('__maineid')), errors)

    def _insert_entity(self, etype, eid, rqlquery):
        rql = rqlquery.insert_query(etype)
        try:
            entity = self._cw.execute(rql, rqlquery.kwargs).get_entity(0, 0)
            neweid = entity.eid
        except ValidationError, ex:
            self._to_create[eid] = ex.entity
            if self._cw.json_request: # XXX (syt) why?
                ex.entity = eid
            raise
        self._to_create[eid] = neweid
        return neweid

    def _update_entity(self, eid, rqlquery):
        self._cw.execute(rqlquery.update_query(eid), rqlquery.kwargs)

    def edit_entity(self, formparams, multiple=False):
        """edit / create / copy an entity and return its eid"""
        etype = formparams['__type']
        entity = self._cw.vreg['etypes'].etype_class(etype)(self._cw)
        entity.eid = valerror_eid(formparams['eid'])
        is_main_entity = self._cw.form.get('__maineid') == formparams['eid']
        # let a chance to do some entity specific stuff
        entity.cw_adapt_to('IEditControl').pre_web_edit()
        # create a rql query from parameters
        rqlquery = RqlQuery()
        # process inlined relations at the same time as attributes
        # this will generate less rql queries and might be useful in
        # a few dark corners
        formid = self._cw.form.get('__form_id', 'edition')
        form = self._cw.vreg['forms'].select(formid, self._cw, entity=entity)
        eid = form.actual_eid(entity.eid)
        form.formvalues = {} # init fields value cache
        try:
            editedfields = formparams['_cw_edited_fields']
        except KeyError:
            raise RequestError(self._cw._('no edited fields specified for entity %s' % entity.eid))
        for editedfield in splitstrip(editedfields):
            try:
                name, role = editedfield.split('-')
            except:
                name = editedfield
                role = None
            if form.field_by_name.im_func.func_code.co_argcount == 4: # XXX
                field = form.field_by_name(name, role, eschema=entity.e_schema)
            else:
                field = form.field_by_name(name, role)
            if field.has_been_modified(form):
                self.handle_formfield(form, field, rqlquery)
        if self.errors:
            errors = dict((f.role_name(), unicode(ex)) for f, ex in self.errors)
            raise ValidationError(valerror_eid(entity.eid), errors)
        if eid is None: # creation or copy
            entity.eid = self._insert_entity(etype, formparams['eid'], rqlquery)
        elif rqlquery.edited: # edition of an existant entity
            self._update_entity(eid, rqlquery)
        if is_main_entity:
            self.notify_edited(entity)
        if formparams.has_key('__delete'):
            # XXX deprecate?
            todelete = self._cw.list_form_param('__delete', formparams, pop=True)
            autoform.delete_relations(self._cw, todelete)
        if formparams.has_key('__cloned_eid'):
            entity.copy_relations(typed_eid(formparams['__cloned_eid']))
        if is_main_entity: # only execute linkto for the main entity
            self.execute_linkto(entity.eid)
        return eid

    def handle_formfield(self, form, field, rqlquery=None):
        eschema = form.edited_entity.e_schema
        try:
            for field, value in field.process_posted(form):
                if not (
                    (field.role == 'subject' and field.name in eschema.subjrels)
                    or
                    (field.role == 'object' and field.name in eschema.objrels)):
                    continue
                rschema = self._cw.vreg.schema.rschema(field.name)
                if rschema.final:
                    rqlquery.kwargs[field.name] = value
                    rqlquery.edited.append('X %s %%(%s)s' % (rschema, rschema))
                else:
                    if form.edited_entity.has_eid():
                        origvalues = set(entity.eid for entity in form.edited_entity.related(field.name, field.role, entities=True))
                    else:
                        origvalues = set()
                    if value is None or value == origvalues:
                        continue # not edited / not modified / to do later
                    if rschema.inlined and rqlquery is not None and field.role == 'subject':
                        self.handle_inlined_relation(form, field, value, origvalues, rqlquery)
                    elif form.edited_entity.has_eid():
                        self.handle_relation(form, field, value, origvalues)
                    else:
                        self._pending_fields.add( (form, field) )

        except ProcessFormError, exc:
            self.errors.append((field, exc))

    def handle_inlined_relation(self, form, field, values, origvalues, rqlquery):
        """handle edition for the (rschema, x) relation of the given entity
        """
        attr = field.name
        if values:
            rqlquery.kwargs[attr] = iter(values).next()
            rqlquery.edited.append('X %s %s' % (attr, attr.upper()))
            rqlquery.restrictions.append('%s eid %%(%s)s' % (attr.upper(), attr))
        elif form.edited_entity.has_eid():
            self.handle_relation(form, field, values, origvalues)

    def handle_relation(self, form, field, values, origvalues):
        """handle edition for the (rschema, x) relation of the given entity
        """
        etype = form.edited_entity.e_schema
        rschema = self._cw.vreg.schema.rschema(field.name)
        if field.role == 'subject':
            desttype = rschema.objects(etype)[0]
            card = rschema.rdef(etype, desttype).cardinality[0]
            subjvar, objvar = 'X', 'Y'
        else:
            desttype = rschema.subjects(etype)[0]
            card = rschema.rdef(desttype, etype).cardinality[1]
            subjvar, objvar = 'Y', 'X'
        eid = form.edited_entity.eid
        if field.role == 'object' or not rschema.inlined or not values:
            # this is not an inlined relation or no values specified,
            # explicty remove relations
            rql = 'DELETE %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in origvalues.difference(values):
                self.relations_rql.append((rql, {'x': eid, 'y': reid}))
        seteids = values.difference(origvalues)
        if seteids:
            rql = 'SET %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in seteids:
                self.relations_rql.append((rql, {'x': eid, 'y': reid}))

    def delete_entities(self, eidtypes):
        """delete entities from the repository"""
        redirect_info = set()
        eidtypes = tuple(eidtypes)
        for eid, etype in eidtypes:
            entity = self._cw.entity_from_eid(eid, etype)
            path, params = entity.cw_adapt_to('IEditControl').after_deletion_path()
            redirect_info.add( (path, tuple(params.iteritems())) )
            entity.cw_delete()
        if len(redirect_info) > 1:
            # In the face of ambiguity, refuse the temptation to guess.
            self._after_deletion_path = 'view', ()
        else:
            self._after_deletion_path = iter(redirect_info).next()
        if len(eidtypes) > 1:
            self._cw.set_message(self._cw._('entities deleted'))
        else:
            self._cw.set_message(self._cw._('entity deleted'))

    def _action_apply(self):
        self._default_publish()
        self.reset()

    def _action_cancel(self):
        errorurl = self._cw.form.get('__errorurl')
        if errorurl:
            self._cw.cancel_edition(errorurl)
        self._cw.set_message(self._cw._('edit canceled'))
        return self.reset()

    def _action_delete(self):
        self.delete_entities(self._cw.edited_eids(withtype=True))
        return self.reset()
