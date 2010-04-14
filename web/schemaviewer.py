"""an helper class to display CubicWeb schema using ureports

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.ureports import Section, Title, Table, Link, Span, Text

from yams.schema2dot import CARD_MAP
from yams.schema import RelationDefinitionSchema

I18NSTRINGS = [_('read'), _('add'), _('delete'), _('update'), _('order')]


class SchemaViewer(object):
    """return an ureport layout for some part of a schema"""
    def __init__(self, req=None, encoding=None):
        self.req = req
        if req is not None:
            self.req.add_css('cubicweb.schema.css')
            if not encoding:
                encoding = req.encoding
        self.encoding = encoding

    def visit_schema(self, schema, display_relations=0, skiptypes=()):
        """get a layout for a whole schema"""
        title = Title(self.req._('Schema %s') % schema.name,
                      klass='titleUnderline')
        layout = Section(children=(title,))
        esection = Section(children=(Title(self.req._('Entities'),
                                           klass='titleUnderline'),))
        layout.append(esection)
        eschemas = [eschema for eschema in schema.entities()
                    if not (eschema.final or eschema in skiptypes)]
        for eschema in sorted(eschemas):
            esection.append(self.visit_entityschema(eschema, skiptypes))
        if display_relations:
            title = Title(self.req._('Relations'), klass='titleUnderline')
            rsection = Section(children=(title,))
            layout.append(rsection)
            relations = [rschema for rschema in schema.relations()
                         if not (rschema.final or rschema.type in skiptypes)]
            keys = [(rschema.type, rschema) for rschema in relations]
            for key, rschema in sorted(keys):
                relstr = self.visit_relationschema(rschema)
                rsection.append(relstr)
        return layout

    def _entity_attributes_data(self, eschema):
        _ = self.req._
        data = [_('attribute'), _('type'), _('default'), _('constraints')]
        for rschema, aschema in eschema.attribute_definitions():
            rdef = eschema.rdef(rschema)
            if not rdef.may_have_permission('read', self.req):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            data.append('%s (%s)' % (aname, _(aname)))
            data.append(_(aschema.type))
            defaultval = eschema.default(aname)
            if defaultval is not None:
                default = self.to_string(defaultval)
            elif rdef.cardinality[0] == '1':
                default = _('required field')
            else:
                default = ''
            data.append(default)
            constraints = rschema.rproperty(eschema.type, aschema.type,
                                            'constraints')
            data.append(', '.join(str(constr) for constr in constraints))
        return data

    def eschema_link_url(self, eschema):
        return self.req.build_url('cwetype/%s' % eschema)

    def rschema_link_url(self, rschema):
        return self.req.build_url('cwrtype/%s' % rschema)

    def stereotype(self, name):
        return Span((' <<%s>>' % name,), klass='stereotype')

    def visit_entityschema(self, eschema, skiptypes=()):
        """get a layout for an entity schema"""
        etype = eschema.type
        layout = Section(children=' ', klass='clear')
        layout.append(Link(etype,'&#160;' , id=etype)) # anchor
        title = Link(self.eschema_link_url(eschema), etype)
        boxchild = [Section(children=(title,), klass='title')]
        data = []
        data.append(Section(children=boxchild, klass='box'))
        data.append(Section(children='', klass='vl'))
        data.append(Section(children='', klass='hl'))
        t_vars = []
        rels = []
        first = True
        for rschema, targetschemas, role in eschema.relation_definitions():
            if rschema.type in skiptypes:
                continue
            rschemaurl = self.rschema_link_url(rschema)
            for oeschema in targetschemas:
                rdef = rschema.role_rdef(eschema, oeschema, role)
                if not rdef.may_have_permission('read', self.req):
                    continue
                label = rschema.type
                if role == 'subject':
                    cards = rschema.rproperty(eschema, oeschema, 'cardinality')
                else:
                    cards = rschema.rproperty(oeschema, eschema, 'cardinality')
                    cards = cards[::-1]
                label = '%s %s %s' % (CARD_MAP[cards[1]], label,
                                      CARD_MAP[cards[0]])
                rlink = Link(rschemaurl, label)
                elink = Link(self.eschema_link_url(oeschema), oeschema.type)
                if first:
                    t_vars.append(Section(children=(elink,), klass='firstvar'))
                    rels.append(Section(children=(rlink,), klass='firstrel'))
                    first = False
                else:
                    t_vars.append(Section(children=(elink,), klass='var'))
                    rels.append(Section(children=(rlink,), klass='rel'))
        data.append(Section(children=rels, klass='rels'))
        data.append(Section(children=t_vars, klass='vars'))
        layout.append(Section(children=data, klass='entityAttributes'))
        return layout

    def visit_relationschema(self, rschema, title=True):
        """get a layout for a relation schema"""
        _ = self.req._
        if title:
            title = Link(self.rschema_link_url(rschema), rschema.type)
            stereotypes = []
            if rschema.meta:
                stereotypes.append('meta')
            if rschema.symmetric:
                stereotypes.append('symmetric')
            if rschema.inlined:
                stereotypes.append('inlined')
            title = Section(children=(title, ' (%s)'%rschema.display_name(self.req)), klass='title')
            if stereotypes:
                title.append(self.stereotype(','.join(stereotypes)))
            layout = Section(children=(title,), klass='schema')
        else:
            layout = Section(klass='schema')
        data = [_('from'), _('to')]
        schema = rschema.schema
        rschema_objects = rschema.objects()
        if rschema_objects:
            # might be empty
            properties = [p for p in RelationDefinitionSchema.rproperty_defs(rschema_objects[0])
                          if not p in ('cardinality', 'composite', 'eid')]
        else:
            properties = []
        data += [_(prop) for prop in properties]
        cols = len(data)
        done = set()
        for subjtype, objtypes in rschema.associations():
            for objtype in objtypes:
                if (subjtype, objtype) in done:
                    continue
                done.add((subjtype, objtype))
                if rschema.symmetric:
                    done.add((objtype, subjtype))
                data.append(Link(self.eschema_link_url(schema[subjtype]), subjtype))
                data.append(Link(self.eschema_link_url(schema[objtype]), objtype))
                rdef = rschema.rdef(subjtype, objtype)
                for prop in properties:
                    val = getattr(rdef, prop)
                    if val is None:
                        val = ''
                    elif prop == 'constraints':
                        val = ', '.join([c.restriction for c in val])
                    elif isinstance(val, (list, tuple)):
                        val = ', '.join(str(v) for v in val)
                    elif val and isinstance(val, basestring):
                        val = _(val)
                    else:
                        val = str(val)
                    data.append(Text(val))
        table = Table(cols=cols, rheaders=1, children=data, klass='listing')
        layout.append(Section(children=(table,), klass='relationDefinition'))
        layout.append(Section(children='', klass='clear'))
        return layout

    def to_string(self, value):
        """used to converte arbitrary values to encoded string"""
        if isinstance(value, unicode):
            return value.encode(self.encoding, 'replace')
        return str(value)
