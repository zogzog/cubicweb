# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""produces some Ontology Web Language schema and views

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import TransformError, xml_escape

from cubicweb.view import StartupView, EntityView
from cubicweb.predicates import none_rset, match_view
from cubicweb.web.action import Action
from cubicweb.web.views import schema

OWL_CARD_MAP = {'1': '<rdf:type rdf:resource="&owl;FunctionalProperty"/>',
                '?': '<owl:maxCardinality rdf:datatype="&xsd;int">1</owl:maxCardinality>',
                '+': '<owl:minCardinality rdf:datatype="&xsd;int">1</owl:minCardinality>',
                '*': ''
                }

OWL_TYPE_MAP = {'String': 'xsd:string',
                'Bytes': 'xsd:byte',
                'Password': 'xsd:byte',

                'Boolean': 'xsd:boolean',
                'Int': 'xsd:int',
                'BigInt': 'xsd:int',
                'Float': 'xsd:float',
                'Decimal' : 'xsd:decimal',

                'Date':'xsd:date',
                'Datetime': 'xsd:dateTime',
                'TZDatetime': 'xsd:dateTime',
                'Time': 'xsd:time',
                'TZTime': 'xsd:time',
                'Interval': 'xsd:duration'
                }

OWL_OPENING_ROOT = u'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE rdf:RDF [
        <!ENTITY owl "http://www.w3.org/2002/07/owl#" >
        <!ENTITY xsd "http://www.w3.org/2001/XMLSchema#" >
]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
    xmlns:owl="http://www.w3.org/2002/07/owl#"
    xmlns="http://logilab.org/owl/ontologies/%(appid)s#"
    xmlns:%(appid)s="http://logilab.org/owl/ontologies/%(appid)s#"
    xmlns:base="http://logilab.org/owl/ontologies/%(appid)s">

  <owl:Ontology rdf:about="">
    <rdfs:comment>
    %(appid)s Cubicweb OWL Ontology
    </rdfs:comment>
  </owl:Ontology>'''

OWL_CLOSING_ROOT = u'</rdf:RDF>'


class OWLView(StartupView):
    """This view export in owl format schema database. It is the TBOX"""
    __regid__ = 'owl'
    title = _('owl')
    templatable = False
    content_type = 'application/xml' # 'text/xml'

    def call(self, writeprefix=True):
        skipmeta = int(self._cw.form.get('skipmeta', True))
        if writeprefix:
            self.w(OWL_OPENING_ROOT % {'appid': self._cw.vreg.schema.name})
        self.visit_schema(skiptypes=skipmeta and schema.SKIP_TYPES or ())
        if writeprefix:
            self.w(OWL_CLOSING_ROOT)

    def should_display_rschema(self, eschema, rschema, role):
        return not rschema in self.skiptypes and (
            rschema.may_have_permission('read', self._cw, eschema, role))

    def visit_schema(self, skiptypes):
        """get a layout for a whole schema"""
        self.skiptypes = skiptypes
        entities = sorted(eschema for eschema in self._cw.vreg.schema.entities()
                          if not eschema.final or eschema in skiptypes)
        self.w(u'<!-- classes definition -->')
        for eschema in entities:
            self.visit_entityschema(eschema)
            self.w(u'<!-- property definition -->')
            self.visit_property_schema(eschema)
            self.w(u'<!-- datatype property -->')
            self.visit_property_object_schema(eschema)

    def visit_entityschema(self, eschema):
        """get a layout for an entity OWL schema"""
        self.w(u'<owl:Class rdf:ID="%s">'% eschema)
        self.w(u'<!-- relations -->')
        for rschema, targetschemas, role in eschema.relation_definitions():
            if not self.should_display_rschema(eschema, rschema, role):
                continue
            for oeschema in targetschemas:
                card = rschema.role_rdef(eschema, oeschema, role).role_cardinality(role)
                cardtag = OWL_CARD_MAP[card]
                if cardtag:
                    self.w(u'''<rdfs:subClassOf>
 <owl:Restriction>
  <owl:onProperty rdf:resource="#%s"/>
  %s
 </owl:Restriction>
</rdfs:subClassOf>''' % (rschema, cardtag))

        self.w(u'<!-- attributes -->')
        for rschema, aschema in eschema.attribute_definitions():
            if not self.should_display_rschema(eschema, rschema, 'subject'):
                continue
            self.w(u'''<rdfs:subClassOf>
  <owl:Restriction>
   <owl:onProperty rdf:resource="#%s"/>
   <rdf:type rdf:resource="&owl;FunctionalProperty"/>
  </owl:Restriction>
</rdfs:subClassOf>''' % rschema)
        self.w(u'</owl:Class>')

    def visit_property_schema(self, eschema):
        """get a layout for property entity OWL schema"""
        for rschema, targetschemas, role in eschema.relation_definitions():
            if not self.should_display_rschema(eschema, rschema, role):
                continue
            for oeschema in targetschemas:
                self.w(u'''<owl:ObjectProperty rdf:ID="%s">
 <rdfs:domain rdf:resource="#%s"/>
 <rdfs:range rdf:resource="#%s"/>
</owl:ObjectProperty>''' % (rschema, eschema, oeschema.type))

    def visit_property_object_schema(self, eschema):
        for rschema, aschema in eschema.attribute_definitions():
            if not self.should_display_rschema(eschema, rschema, 'subject'):
                continue
            self.w(u'''<owl:DatatypeProperty rdf:ID="%s">
  <rdfs:domain rdf:resource="#%s"/>
  <rdfs:range rdf:resource="%s"/>
</owl:DatatypeProperty>''' % (rschema, eschema, OWL_TYPE_MAP[aschema.type]))


class OWLABOXView(EntityView):
    '''This view represents a part of the ABOX for a given entity.'''
    __regid__ = 'owlabox'
    title = _('owlabox')
    templatable = False
    content_type = 'application/xml' # 'text/xml'

    def call(self):
        self.w(OWL_OPENING_ROOT % {'appid': self._cw.vreg.schema.name})
        for i in xrange(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self.w(OWL_CLOSING_ROOT)

    def cell_call(self, row, col):
        self.wview('owlaboxitem', self.cw_rset, row=row, col=col)


class OWLABOXItemView(EntityView):
    '''This view represents a part of the ABOX for a given entity.'''
    __regid__ = 'owlaboxitem'
    templatable = False
    content_type = 'application/xml' # 'text/xml'

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        eschema = entity.e_schema
        self.w(u'<%s rdf:ID="%s">' % (eschema, entity.eid))
        self.w(u'<!--attributes-->')
        for rschema, aschema in eschema.attribute_definitions():
            if rschema.meta:
                continue
            rdef = rschema.rdef(eschema, aschema)
            if not rdef.may_have_permission('read', self._cw):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            try:
                attr = entity.printable_value(aname, format='text/plain')
                if attr:
                    self.w(u'<%s>%s</%s>' % (aname, xml_escape(attr), aname))
            except TransformError:
                pass
        self.w(u'<!--relations -->')
        for rschema, targetschemas, role in eschema.relation_definitions():
            if rschema.meta:
                continue
            for tschema in targetschemas:
                rdef = rschema.role_rdef(eschema, tschema, role)
                if rdef.may_have_permission('read', self._cw):
                    break
            else:
                # no read perms to any relation of this type. Skip.
                continue
            if role == 'object':
                attr = 'reverse_%s' % rschema.type
            else:
                attr = rschema.type
            for x in getattr(entity, attr):
                self.w(u'<%s>%s %s</%s>' % (attr, x.__regid__, x.eid, attr))
        self.w(u'</%s>'% eschema)


class DownloadOWLSchemaAction(Action):
    __regid__ = 'download_as_owl'
    __select__ = none_rset() & match_view('schema')

    category = 'mainactions'
    title = _('download schema as owl')

    def url(self):
        return self._cw.build_url('view', vid='owl')
