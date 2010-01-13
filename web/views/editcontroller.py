"""The edit controller, handling form submitting.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from rql.utils import rqlvar_maker

from logilab.common.textutils import splitstrip

from cubicweb import Binary, ValidationError, typed_eid
from cubicweb.web import INTERNAL_FIELD_VALUE, RequestError, NothingToEdit, ProcessFormError
from cubicweb.web.controller import parse_relations_descr
from cubicweb.web.views.basecontrollers import ViewController


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


class EditController(ViewController):
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
            req.set_shared_data('__maineid', form['__maineid'], querydata=True)
        # no specific action, generic edition
        self._to_create = req.data['eidmap'] = {}
        self._pending_fields = req.data['pendingfields'] = set()
        todelete = self._cw.get_pending_deletes()
        toinsert = self._cw.get_pending_inserts()
        try:
            methodname = req.form.pop('__method', None)
            for eid in req.edited_eids():
                # __type and eid
                formparams = req.extract_entity_params(eid, minparams=2)
                if methodname is not None:
                    entity = req.entity_from_eid(eid)
                    method = getattr(entity, methodname)
                    method(formparams)
                eid = self.edit_entity(formparams)
        except (RequestError, NothingToEdit), ex:
            if '__linkto' in req.form and 'eid' in req.form:
                self.execute_linkto()
            elif not ('__delete' in req.form or '__insert' in req.form or todelete or toinsert):
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
            todelete += req.list_form_param('__delete', req.form, pop=True)
        if todelete:
            self.delete_relations(parse_relations_descr(todelete))
        if req.form.has_key('__insert'):
            toinsert = req.list_form_param('__insert', req.form, pop=True)
        if toinsert:
            self.insert_relations(parse_relations_descr(toinsert))
        self._cw.remove_pending_operations()
        if self.errors:
            errors = dict((f.name, unicode(ex)) for f, ex in self.errors)
            raise ValidationError(form.get('__maineid'), errors)

    def _insert_entity(self, etype, eid, rqlquery):
        rql = rqlquery.insert_query(etype)
        try:
            # get the new entity (in some cases, the type might have
            # changed as for the File --> Image mutation)
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
        entity.eid = formparams['eid']
        is_main_entity = self._cw.form.get('__maineid') == formparams['eid']
        # let a chance to do some entity specific stuff
        entity.pre_web_edit()
        # create a rql query from parameters
        rqlquery = RqlQuery()
        # process inlined relations at the same time as attributes
        # this will generate less rql queries and might be useful in
        # a few dark corners
        formid = self._cw.form.get('__form_id', 'edition')
        form = self._cw.vreg['forms'].select(formid, self._cw, entity=entity)
        eid = form.actual_eid(entity.eid)
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
            raise ValidationError(entity.eid, errors)
        if eid is None: # creation or copy
            entity.eid = self._insert_entity(etype, formparams['eid'], rqlquery)
        elif rqlquery.edited: # edition of an existant entity
            self._update_entity(eid, rqlquery)
        if is_main_entity:
            self.notify_edited(entity)
        if formparams.has_key('__delete'):
            todelete = self._cw.list_form_param('__delete', formparams, pop=True)
            self.delete_relations(parse_relations_descr(todelete))
        if formparams.has_key('__cloned_eid'):
            entity.copy_relations(typed_eid(formparams['__cloned_eid']))
        if formparams.has_key('__insert'):
            toinsert = self._cw.list_form_param('__insert', formparams, pop=True)
            self.insert_relations(parse_relations_descr(toinsert))
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
                    if rschema.inlined and rqlquery is not None:
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
                self.relations_rql.append((rql, {'x': eid, 'y': reid}, ('x', 'y')))
        seteids = values.difference(origvalues)
        if seteids:
            rql = 'SET %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in seteids:
                self.relations_rql.append((rql, {'x': eid, 'y': reid}, ('x', 'y')))

    def _action_apply(self):
        self._default_publish()
        self.reset()

    def _action_cancel(self):
        errorurl = self._cw.form.get('__errorurl')
        if errorurl:
            self._cw.cancel_edition(errorurl)
        self._cw.message = self._cw._('edit canceled')
        return self.reset()

    def _action_delete(self):
        self.delete_entities(self._cw.edited_eids(withtype=True))
        return self.reset()


