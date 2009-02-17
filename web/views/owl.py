from logilab.mtconverter import TransformError, html_escape

from cubicweb.common.view import StartupView
from cubicweb.common.view import EntityView

_ = unicode

OWL_CARD_MAP = {'1': '<rdf:type rdf:resource="&owl;FunctionalProperty"/>',                      
                '?': '<owl:maxCardinality rdf:datatype="&xsd;int">1</owl:maxCardinality>',
                '+': '<owl:minCardinality rdf:datatype="&xsd;int">1</owl:minCardinality>',
                '*': ''
                }

OWL_TYPE_MAP = {'String': 'xsd:string',
                'Datetime': 'xsd:dateTime',
                'Bytes': 'xsd:byte',
                'Float': 'xsd:float',
                'Boolean': 'xsd:boolean',
                'Int': 'xsd:int',
                'Date':'xsd:date',
                'Time': 'xsd:time',
                'Password': 'xsd:byte',
                'Decimal' : 'xsd:decimal',
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

DEFAULT_SKIP_RELS = frozenset(('is', 'is_instance_of', 'identity',
                               'owned_by', 'created_by'))

class OWLView(StartupView):
    """This view export in owl format schema database. It is the TBOX"""
    id = 'owl'
    title = _('owl')
    templatable = False
    content_type = 'application/xml' # 'text/xml'

    def call(self, writeprefix=True):
        skipmeta = int(self.req.form.get('skipmeta', True))
        if writeprefix:
            self.w(OWL_OPENING_ROOT % {'appid': self.schema.name})
        self.visit_schema(skipmeta=skipmeta)
        if writeprefix:
            self.w(OWL_CLOSING_ROOT)
        
    def visit_schema(self, skiprels=DEFAULT_SKIP_RELS, skipmeta=True):
        """get a layout for a whole schema"""
        entities = sorted([eschema for eschema in self.schema.entities()
                           if not eschema.is_final()])
        if skipmeta:
            entities = [eschema for eschema in entities
                        if not eschema.meta]
        self.w(u'<!-- classes definition -->')
        for eschema in entities:
            self.visit_entityschema(eschema, skiprels)
            self.w(u'<!-- property definition -->')
            self.visit_property_schema(eschema, skiprels)
            self.w(u'<!-- datatype property -->')
            self.visit_property_object_schema(eschema)

    def visit_entityschema(self, eschema, skiprels=()):
        """get a layout for an entity OWL schema"""
        self.w(u'<owl:Class rdf:ID="%s">'% eschema)         
        self.w(u'<!-- relations -->')    
        for rschema, targetschemas, role in eschema.relation_definitions():
            if rschema.type in skiprels:
                continue
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            for oeschema in targetschemas:
                label = rschema.type
                if role == 'subject':
                    card = rschema.rproperty(eschema, oeschema, 'cardinality')[0]
                else:
                    card = rschema.rproperty(oeschema, eschema, 'cardinality')[1]
                cardtag = OWL_CARD_MAP[card]
                if cardtag:
                    self.w(u'''<rdfs:subClassOf>
 <owl:Restriction>
  <owl:onProperty rdf:resource="#%s"/>
  %s
 </owl:Restriction>
</rdfs:subClassOf>
''' % (label, cardtag))

        self.w(u'<!-- attributes -->')
              
        for rschema, aschema in eschema.attribute_definitions():
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            self.w(u'''<rdfs:subClassOf>
  <owl:Restriction>
   <owl:onProperty rdf:resource="#%s"/>
   <rdf:type rdf:resource="&owl;FunctionalProperty"/>
  </owl:Restriction>
</rdfs:subClassOf>'''                         
                   % aname)
        self.w(u'</owl:Class>')
    
    def visit_property_schema(self, eschema, skiprels=()):
        """get a layout for property entity OWL schema"""
        for rschema, targetschemas, role in eschema.relation_definitions():
            if rschema.type in skiprels:
                continue
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            for oeschema in targetschemas:
                label = rschema.type
                self.w(u'''<owl:ObjectProperty rdf:ID="%s">
 <rdfs:domain rdf:resource="#%s"/>
 <rdfs:range rdf:resource="#%s"/>
</owl:ObjectProperty>                                                
''' % (label, eschema, oeschema.type))

    def visit_property_object_schema(self, eschema):
        for rschema, aschema in eschema.attribute_definitions():
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            self.w(u'''<owl:DatatypeProperty rdf:ID="%s">
  <rdfs:domain rdf:resource="#%s"/>
  <rdfs:range rdf:resource="%s"/>
</owl:DatatypeProperty>'''
                   % (aname, eschema, OWL_TYPE_MAP[aschema.type]))

            
class OWLABOXView(EntityView):
    '''This view represents a part of the ABOX for a given entity.'''
    
    id = 'owlabox'
    title = _('owlabox')
    templatable = False
    content_type = 'application/xml' # 'text/xml'
    
    def call(self):
        self.w(OWL_OPENING_ROOT % {'appid': self.schema.name})
        self.wview('owl', None, writeprefix=False)
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self.w(OWL_CLOSING_ROOT)

    def cell_call(self, row, col, skiprels=DEFAULT_SKIP_RELS):
        self.wview('owlaboxitem', self.rset, row=row, col=col, skiprels=skiprels)

        
class OWLABOXItemView(EntityView):
    '''This view represents a part of the ABOX for a given entity.'''    
    id = 'owlaboxitem'
    templatable = False
    content_type = 'application/xml' # 'text/xml'

    def cell_call(self, row, col, skiprels=DEFAULT_SKIP_RELS):
        entity = self.complete_entity(row, col)
        eschema = entity.e_schema
        self.w(u'<%s rdf:ID="%s">' % (eschema, entity.eid))
        self.w(u'<!--attributes-->')
        for rschema, aschema in eschema.attribute_definitions():
            if rschema.type in skiprels:
                continue
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            try:
                attr = entity.printable_value(aname, format='text/plain')
                if attr:
                    self.w(u'<%s>%s</%s>' % (aname, html_escape(attr), aname))
            except TransformError:
                pass
        self.w(u'<!--relations -->')
        for rschema, targetschemas, role in eschema.relation_definitions():
            if rschema.type in skiprels:
                continue
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            if role == 'object':
                attr = 'reverse_%s' % rschema.type 
            else:
                attr = rschema.type        
            for x in getattr(entity, attr):
                self.w(u'<%s>%s %s</%s>' % (attr, x.id, x.eid, attr))
        self.w(u'</%s>'% eschema)

