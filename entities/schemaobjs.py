"""schema definition related entities

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached

from cubicweb import ValidationError
from cubicweb.schema import ERQLExpression, RRQLExpression

from cubicweb.entities import AnyEntity, fetch_config


class EEType(AnyEntity):
    id = 'EEType'
    fetch_attrs, fetch_order = fetch_config(['name'])
    __rtags__ = {
        ('final',         '*', 'subject'): 'generated',
        
        ('state_of',      '*', 'object'): 'create',
        ('transition_of', '*', 'object'): 'create',
        ('from_entity',   '*', 'object'): 'link',
        ('to_entity',     '*', 'object'): 'link',
        }
    def dc_title(self):
        return self.req._(self.name)
    
    def dc_long_title(self):
        stereotypes = []
        _ = self.req._
        if self.meta:
            stereotypes.append(_('meta'))
        if self.final:
            stereotypes.append(_('final'))
        if stereotypes:
            return u'%s <<%s>>' % (self.dc_title(), ', '.join(stereotypes))
        return self.dc_title()

    def db_key_name(self):
        """XXX goa specific"""
        return self.get('name')


class ERType(AnyEntity):
    id = 'ERType'
    fetch_attrs, fetch_order = fetch_config(['name'])
    __rtags__ = {
        ('final',         '*', 'subject'): 'generated',
        
        ('relation_type', '*', 'object') : 'create',
        }
    
    def dc_title(self):
        return self.req._(self.name)
    
    def dc_long_title(self):
        stereotypes = []
        _ = self.req._
        if self.meta:
            stereotypes.append(_('meta'))
        if self.symetric:
            stereotypes.append(_('symetric'))
        if self.inlined:
            stereotypes.append(_('inlined'))
        if self.final:
            stereotypes.append(_('final'))
        if stereotypes:
            return u'%s <<%s>>' % (self.dc_title(), ', '.join(stereotypes))
        return self.dc_title()

    def inlined_changed(self, inlined):
        """check inlining is necessary and possible:
        
        * return False if nothing has changed
        * raise ValidationError if inlining is'nt possible
        * eventually return True
        """
        rtype = self.name
        rschema = self.schema.rschema(rtype)
        if inlined == rschema.inlined:
            return False
        if inlined:
            for (stype, otype) in rschema.iter_rdefs():
                card = rschema.rproperty(stype, otype, 'cardinality')[0]
                if not card in '?1':
                    msg = self.req._("can't set inlined=%(inlined)s, "
                                     "%(stype)s %(rtype)s %(otype)s "
                                     "has cardinality=%(card)s")
                    raise ValidationError(self.eid, {'inlined': msg % locals()})
        return True

    def db_key_name(self):
        """XXX goa specific"""
        return self.get('name')


class ENFRDef(AnyEntity):
    id = 'ENFRDef'
    fetch_attrs = fetch_config(['cardinality'])[0]
    __rtags__ = {
        ('relation_type', 'ERType', 'subject') : 'inlineview',
        ('from_entity', 'EEType', 'subject') : 'inlineview',
        ('to_entity', 'EEType', 'subject') : 'inlineview',
        }
    
    def dc_title(self):
        return u'%s %s %s' % (
            self.from_entity[0].name,
            self.relation_type[0].name, 
            self.to_entity[0].name)
    
    def dc_long_title(self):
        card = self.cardinality
        scard, ocard = u'', u''
        if card[0] != '1':
            scard = '[%s]' % card[0]
        if card[1] != '1':
            ocard = '[%s]' % card[1]
        return u'%s %s%s%s %s' % (
            self.from_entity[0].name,
            scard, self.relation_type[0].name, ocard,
            self.to_entity[0].name)

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.relation_type:
            return self.relation_type[0].rest_path(), {}
        return super(ENFRDef, self).after_deletion_path()


class EFRDef(ENFRDef):
    id = 'EFRDef'
    
    def dc_long_title(self):
        card = self.cardinality
        scard = u''
        if card[0] == '1':
            scard = '+'
        return u'%s %s%s %s' % (
            self.from_entity[0].name,
            scard, self.relation_type[0].name, 
            self.to_entity[0].name)


class EConstraint(AnyEntity):
    id = 'EConstraint'
    fetch_attrs, fetch_order = fetch_config(['value'])

    def dc_title(self):
        return '%s(%s)' % (self.cstrtype[0].name, self.value or u'')
        
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.reverse_constrained_by:
            return self.reverse_constrained_by[0].rest_path(), {}
        return super(EConstraint, self).after_deletion_path()

    @property
    def type(self):
        return self.cstrtype[0].name

        
class RQLExpression(AnyEntity):
    id = 'RQLExpression'
    fetch_attrs, fetch_order = fetch_config(['exprtype', 'mainvars', 'expression'])

    widgets = {
        'expression' : "StringWidget",
        }

    def dc_title(self):
        return '%s(%s)' % (self.exprtype, self.expression or u'')

    @property
    def expression_of(self):
        for rel in ('read_permission', 'add_permission', 'delete_permission',
                    'update_permission', 'condition'):
            values = getattr(self, 'reverse_%s' % rel)
            if values:
                return values[0]
            
    @cached
    def _rqlexpr(self):
        if self.exprtype == 'ERQLExpression':
            return ERQLExpression(self.expression, self.mainvars, self.eid)
        #if self.exprtype == 'RRQLExpression':
        return RRQLExpression(self.expression, self.mainvars, self.eid)
    
    def check_expression(self, *args, **kwargs):
        return self._rqlexpr().check(*args, **kwargs)
    
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        if self.expression_of:
            return self.expression_of.rest_path(), {}
        return super(RQLExpression, self).after_deletion_path()


class EPermission(AnyEntity):
    id = 'EPermission'
    fetch_attrs, fetch_order = fetch_config(['name', 'label'])


    __rtags__ = {
        'require_group' : 'primary',
        }

    def dc_title(self):
        if self.label:
            return '%s (%s)' % (self.req._(self.name), self.label)
        return self.req._(self.name)
    
    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        permissionof = getattr(self, 'reverse_require_permission', ())
        if len(permissionof) == 1:
            return permissionof[0].rest_path(), {}
        return super(EPermission, self).after_deletion_path()
