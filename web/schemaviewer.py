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
"""an helper class to display CubicWeb schema using ureports

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.ureports import Section, Title, Table, Link, Span, Text

from yams.schema2dot import CARD_MAP
from yams.schema import RelationDefinitionSchema
from operator import attrgetter

TYPE_GETTER = attrgetter('type')

I18NSTRINGS = [_('read'), _('add'), _('delete'), _('update'), _('order')]


class SchemaViewer(object):
    """return an ureport layout for some part of a schema"""
    def __init__(self, req=None, encoding=None):
        self.req = req
        if req is not None:
            req.add_css('cubicweb.schema.css')
            if encoding is None:
                encoding = req.encoding
            self._ = req._
        else:
            encoding = 'ascii'
            self._ = unicode
        self.encoding = encoding

    # no self.req managements

    def may_read(self, rdef, action):
        """Return true if request user may read the given schema.
        Always return True when no request is provided.
        """
        if self.req is None:
            return True
        return sch.may_have_permission('read', self.req)

    def format_eschema(self, eschema):
        text = eschema.type
        if self.req is None:
            return Text(text)
        return Link(self.req.build_url('cwetype/%s' % eschema), text)

    def format_rschema(self, rschema, label=None):
        if label is None:
            label = rschema.type
        if self.req is None:
            return Text(label)
        return Link(self.req.build_url('cwrtype/%s' % rschema), label)

    # end of no self.req managements

    def visit_schema(self, schema, display_relations=0, skiptypes=()):
        """get a layout for a whole schema"""
        title = Title(self._('Schema %s') % schema.name,
                      klass='titleUnderline')
        layout = Section(children=(title,))
        esection = Section(children=(Title(self._('Entities'),
                                           klass='titleUnderline'),))
        layout.append(esection)
        eschemas = [eschema for eschema in schema.entities()
                    if not (eschema.final or eschema in skiptypes)]
        for eschema in sorted(eschemas, key=TYPE_GETTER):
            esection.append(self.visit_entityschema(eschema, skiptypes))
        if display_relations:
            title = Title(self._('Relations'), klass='titleUnderline')
            rsection = Section(children=(title,))
            layout.append(rsection)
            relations = [rschema for rschema in sorted(schema.relations(), key=TYPE_GETTER)
                         if not (rschema.final or rschema.type in skiptypes)]
            keys = [(rschema.type, rschema) for rschema in relations]
            for key, rschema in sorted(keys, cmp=(lambda x, y: cmp(x[1], y[1]))):
                relstr = self.visit_relationschema(rschema)
                rsection.append(relstr)
        return layout

    def _entity_attributes_data(self, eschema):
        _ = self._
        data = [_('attribute'), _('type'), _('default'), _('constraints')]
        attributes = sorted(eschema.attribute_definitions(), cmp=(lambda x, y: cmp(x[0].type, y[0].type)))
        for rschema, aschema in attributes:
            rdef = eschema.rdef(rschema)
            if not self.may_read(rdef):
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


    def stereotype(self, name):
        return Span((' <<%s>>' % name,), klass='stereotype')

    def visit_entityschema(self, eschema, skiptypes=()):
        """get a layout for an entity schema"""
        etype = eschema.type
        layout = Section(children=' ', klass='clear')
        layout.append(Link(etype,'&#160;' , id=etype)) # anchor
        title = self.format_eschema(eschema)
        boxchild = [Section(children=(title,), klass='title')]
        data = []
        data.append(Section(children=boxchild, klass='box'))
        data.append(Section(children='', klass='vl'))
        data.append(Section(children='', klass='hl'))
        t_vars = []
        rels = []
        first = True

        rel_defs = sorted(eschema.relation_definitions(),
                          cmp=(lambda x, y: cmp((x[0].type, x[0].cardinality),
                          (y[0].type, y[0].cardinality))))
        for rschema, targetschemas, role in rel_defs:
            if rschema.type in skiptypes:
                continue
            for oeschema in sorted(targetschemas, key=TYPE_GETTER):
                rdef = rschema.role_rdef(eschema, oeschema, role)
                if not self.may_read(rdef):
                    continue
                label = rschema.type
                if role == 'subject':
                    cards = rschema.rproperty(eschema, oeschema, 'cardinality')
                else:
                    cards = rschema.rproperty(oeschema, eschema, 'cardinality')
                    cards = cards[::-1]
                label = '%s %s %s' % (CARD_MAP[cards[1]], label,
                                      CARD_MAP[cards[0]])
                rlink = self.format_rschema(rschema, label)
                elink = self.format_eschema(oeschema)
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
        _ = self._
        if title:
            title = self.format_rschema(rschema)
            stereotypes = []
            if rschema.meta:
                stereotypes.append('meta')
            if rschema.symmetric:
                stereotypes.append('symmetric')
            if rschema.inlined:
                stereotypes.append('inlined')
            title = Section(children=(title,), klass='title')
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
        for subjtype, objtypes in sorted(rschema.associations()):
            for objtype in objtypes:
                if (subjtype, objtype) in done:
                    continue
                done.add((subjtype, objtype))
                if rschema.symmetric:
                    done.add((objtype, subjtype))
                data.append(self.format_eschema(schema[subjtype]))
                data.append(self.format_eschema(schema[objtype]))
                rdef = rschema.rdef(subjtype, objtype)
                for prop in properties:
                    val = getattr(rdef, prop)
                    if val is None:
                        val = ''
                    elif prop == 'constraints':
                        val = ', '.join([c.restriction for c in val])
                    elif isinstance(val, dict):
                        for key, value in val.iteritems():
                            if isinstance(value, (list, tuple)):
                                val[key] = ', '.join(sorted( str(v) for v in value))
                        val = str(val)

                    elif isinstance(val, (list, tuple)):
                        val = sorted(val)
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
