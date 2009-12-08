"""The edit controller, handling form submitting.

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from decimal import Decimal

from rql.utils import rqlvar_maker

from cubicweb import Binary, ValidationError, typed_eid
from cubicweb.web import INTERNAL_FIELD_VALUE, RequestError, NothingToEdit, ProcessFormError
from cubicweb.web.controller import parse_relations_descr
from cubicweb.web.views.basecontrollers import ViewController


class ToDoLater(Exception):
    """exception used in the edit controller to indicate that a relation
    can't be handled right now and have to be handled later
    """

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
        self._pending_relations = []
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
        except (RequestError, NothingToEdit):
            if '__linkto' in req.form and 'eid' in req.form:
                self.execute_linkto()
            elif not ('__delete' in req.form or '__insert' in req.form or todelete or toinsert):
                raise ValidationError(None, {None: req._('nothing to edit')})
        for querydef in self.relations_rql:
            self._cw.execute(*querydef)
        # handle relations in newly created entities
        # XXX find a way to merge _pending_relations and relations_rql
        if self._pending_relations:
            for form, field, entity in self._pending_relations:
                for querydef in self.handle_relation(form, field, entity, True):
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
        rql = rqlquery.update_query(eid)
        self._cw.execute(rql, rqlquery.kwargs)

    def edit_entity(self, formparams, multiple=False):
        """edit / create / copy an entity and return its eid"""
        etype = formparams['__type']
        entity = self._cw.vreg['etypes'].etype_class(etype)(self._cw)
        entity.eid = formparams['eid']
        eid = self._get_eid(entity.eid)
        is_main_entity = self._cw.form.get('__maineid') == formparams['eid']
        # let a chance to do some entity specific stuff.tn
        entity.pre_web_edit()
        # create a rql query from parameters
        rqlquery = RqlQuery()
        # process inlined relations at the same time as attributes
        # this will generate less rql queries and might be useful in
        # a few dark corners
        formid = self._cw.form.get('__form_id', 'edition')
        form = self._cw.vreg['forms'].select(formid, self._cw, entity=entity)
        for field in form.fields:
            if form.form_field_modified(field):
                self.handle_formfield(form, field, entity, rqlquery)
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
            self.execute_linkto(eid)
        return eid

    def handle_formfield(self, form, field, entity, rqlquery):
        eschema = entity.e_schema
        try:
            for attr, value in field.process_posted(form):
                if not (
                    (field.role == 'subject' and field.name in eschema.subjrels)
                    or
                    (field.role == 'object' and field.name in eschema.objrels)):
                    continue
                rschema = self._cw.vreg.schema.rschema(field.name)
                if rschema.final:
                    rqlquery.kwargs[attr] = value
                    rqlquery.edited.append('X %s %%(%s)s' % (attr, attr))
                elif rschema.inlined:
                    self.handle_inlined_relation(form, field, entity, rqlquery)
                else:
                    self.relations_rql += self.handle_relation(
                        form, field, entity)
        except ProcessFormError, exc:
            self.errors.append((field, exc))

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

    def _relation_values(self, form, field, entity, late=False):
        """handle edition for the (rschema, x) relation of the given entity
        """
        values = set()
        for eid in field.process_form_value(form):
            if not eid: # AutoCompletionWidget
                continue
            typed_eid = self._get_eid(eid)
            if typed_eid is None:
                if late:
                    # eid is still None while it's already a late call
                    # this mean that the associated entity has not been created
                    raise Exception("eid %s is still not created" % eid)
                self._pending_relations.append( (form, field, entity) )
                return None
            values.add(typed_eid)
        return values

    def handle_inlined_relation(self, form, field, entity, rqlquery):
        """handle edition for the (rschema, x) relation of the given entity
        """
        origvalues = set(row[0] for row in entity.related(field.name, field.role))
        values  = self._relation_values(form, field, entity)
        if values is None or values == origvalues:
            return # not edited / not modified / to do later
        attr = field.name
        if values:
            rqlquery.kwargs[attr] = iter(values).next()
            rqlquery.edition.append('X %s %s' % (attr, attr.upper()))
            rqlquery.restrictions.append('%s eid %%(%s)s' % (attr.upper(), attr))
        elif entity.has_eid():
            self.relations_rql += self.handle_relation(form, field, entity)

    def handle_relation(self, form, field, entity, late=False):
        """handle edition for the (rschema, x) relation of the given entity
        """
        origvalues = set(row[0] for row in entity.related(field.name, field.role))
        values  = self._relation_values(form, field, entity, late)
        if values is None or values == origvalues:
            return # not edited / not modified / to do later
        etype = entity.e_schema
        rschema = self._cw.vreg.schema.rschema(field.name)
        if field.role == 'subject':
            desttype = rschema.objects(etype)[0]
            card = rschema.rproperty(etype, desttype, 'cardinality')[0]
            subjvar, objvar = 'X', 'Y'
        else:
            desttype = rschema.subjects(etype)[0]
            card = rschema.rproperty(desttype, etype, 'cardinality')[1]
            subjvar, objvar = 'Y', 'X'
        eid = entity.eid
        if field.role == 'object' or not rschema.inlined or not values:
            # this is not an inlined relation or no values specified,
            # explicty remove relations
            rql = 'DELETE %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in origvalues.difference(values):
                yield (rql, {'x': eid, 'y': reid}, ('x', 'y'))
        seteids = values.difference(origvalues)
        if seteids:
            rql = 'SET %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in seteids:
                yield (rql, {'x': eid, 'y': reid}, ('x', 'y'))

    def _get_eid(self, eid):
        # should be either an int (existant entity) or a variable (to be
        # created entity)
        assert eid or eid == 0, repr(eid) # 0 is a valid eid
        try:
            return typed_eid(eid)
        except ValueError:
            try:
                return self._to_create[eid]
            except KeyError:
                self._to_create[eid] = None
                return None

    def _linked_eids(self, eids, late=False):
        """return a list of eids if they are all known, else raise ToDoLater
        """


