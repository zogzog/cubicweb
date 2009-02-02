from logilab.mtconverter import html_escape

from cubicweb.common.view import StartupView
from cubicweb.common.view import EntityView

_ = unicode

OWL_CARD_MAP = {'1': '<rdf:type rdf:resource="&owl;FunctionalProperty"/>',                      
                '?': '<owl:maxCardinality rdf:datatype="&xsd;int">1</owl:maxCardinality>',
                '+': '<owl:minCardinality rdf:datatype="&xsd;int">1</owl:minCardinality>',
                '*': ''
                }

OWL_CARD_MAP_DATA = {'String': 'xsd:string',
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
        <!ENTITY rdfs "http://www.w3.org/2000/01/rdf-schema#" >
        <!ENTITY rdf "http://www.w3.org/1999/02/22-rdf-syntax-ns#" >
        <!ENTITY %s "http://logilab.org/owl/ontologies/%s#" >
        
        ]>        
        <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
            xmlns:xsd="http://www.w3.org/2001/XMLSchema#"
            xmlns:owl="http://www.w3.org/2002/07/owl#"
            xmlns="http://logilab.org/owl/ontologies/%s#"
            xmlns:%s="http://logilab.org/owl/ontologies/%s#"
            xmlns:base="http://logilab.org/owl/ontologies/%s">

    <owl:Ontology rdf:about="">
        <rdfs:comment>
        %s Cubicweb OWL Ontology                           
                                        
        </rdfs:comment>
   </owl:Ontology>'''

OWL_CLOSING_ROOT = u'</rdf:RDF>'

class OWLView(StartupView):
    """This view export in owl format schema database. It is the TBOX"""
    id = 'owl'
    title = _('owl')
    templatable =False
    content_type = 'application/xml' # 'text/xml'

    def call(self):
        
        skipmeta = int(self.req.form.get('skipmeta', True))
        self.w(OWL_OPENING_ROOT % (self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name))
        self.wview('tbox', None, writeprefix=False)
        entities = [eschema for eschema in self.schema.entities()
                    if not eschema.is_final()]
        if skipmeta:
            entities = [eschema for eschema in entities
                        if not eschema.meta]
        for entity in entities:
            rql = 'Any X where X is %s'
            rset = self.req.execute(rql% entity)
            if rset:
                self.wview('owlaboxlight', rset, writeprefix=False)
        self.w(OWL_CLOSING_ROOT)

class TBoxView(StartupView):
    """This view export in owl format the whole cubicweb ontologie. First part is the TBOX, second part is an ABOX ligth version."""
    id = 'tbox'
    title = _('tbox')
    templatable =False
    content_type = 'application/xml' # 'text/xml'

    def call(self, writeprefix=True):
        skipmeta = int(self.req.form.get('skipmeta', True))
        if writeprefix:
            self.w(OWL_OPENING_ROOT % (self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name) )
              
        self.visit_schema(display_relations=True,
                             skiprels=('is', 'is_instance_of', 'identity',
                                       'owned_by', 'created_by'),
                             skipmeta=skipmeta)
        if writeprefix:
            self.w(OWL_CLOSING_ROOT)
        
    def visit_schema(self, display_relations=0,
                     skiprels=(), skipmeta=True):
        """get a layout for a whole schema"""
        
        entities = [eschema for eschema in self.schema.entities()
                    if not eschema.is_final()]
        if skipmeta:
            entities = [eschema for eschema in entities
                        if not eschema.meta]
        keys = [(eschema.type, eschema) for eschema in entities]
        self.w(u'<!-- classes definition -->')
        for key, eschema in sorted(keys):
            self.visit_entityschema(eschema, skiprels)
        self.w(u'<!-- property definition -->')
        self.w(u'<!-- object property -->')
        for key, eschema in sorted(keys):
             self.visit_property_schema(eschema, skiprels)
        self.w(u'<!-- datatype property -->')
        for key, eschema in sorted(keys):
            self.visit_property_object_schema(eschema, skiprels)
         
    def stereotype(self, name):
        return Span((' <<%s>>' % name,), klass='stereotype')
                       
    def visit_entityschema(self, eschema, skiprels=()):
        """get a layout for an entity OWL schema"""
        etype = eschema.type
        
        if eschema.meta:
            self.stereotype('meta')
            self.w(u'''<owl:Class rdf:ID="%s"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                '''%eschema, stereotype)
        else:
             self.w(u'''<owl:Class rdf:ID="%s"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                '''% eschema)         
       
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
                self.w(u'''<rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#%s"/>
                                %s
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                ''' % (label, OWL_CARD_MAP[card]))

        self.w(u'<!-- attributes -->')
              
        for rschema, aschema in eschema.attribute_definitions():
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            card_data = aschema.type
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
        etype = eschema.type

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
                             
                                ''' % (label, eschema, oeschema.type ))

    def visit_property_object_schema(self, eschema, skiprels=()):
               
        for rschema, aschema in eschema.attribute_definitions():
            if not (rschema.has_local_role('read') or rschema.has_perm(self.req, 'read')):
                continue
            aname = rschema.type
            if aname == 'eid':
                continue
            card_data = aschema.type
            self.w(u'''<owl:DatatypeProperty rdf:ID="%s">
                          <rdfs:domain rdf:resource="#%s"/>
                          <rdfs:range rdf:resource="%s"/>
                       </owl:DatatypeProperty>'''
                   % (aname, eschema, OWL_CARD_MAP_DATA[card_data]))
            
class OWLABOXLightView(EntityView):
    '''This view represents the lihgt part of the ABOX for a given entity'''
    id = 'owlaboxlight'
    title = _('owlaboxlight')
    templatable =False
    accepts = ('Any',)
    content_type = 'application/xml' # 'text/xml'
    
    def call(self, writeprefix=True):

        skipmeta = int(self.req.form.get('skipmeta', True))
        if writeprefix:
            self.w(OWL_OPENING_ROOT % (self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name))
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0, skiprels=('is', 'is_instance_of', 'identity',
                                       'owned_by', 'created_by'),
                             skipmeta=skipmeta)
        if writeprefix:
            self.w(OWL_CLOSING_ROOT)
        

    def cell_call(self, row, col, skiprels=(), skipmeta=True):
        entity = self.complete_entity(row, col)
        eschema = entity.e_schema
        self.w(u'<%s rdf:ID="%s">' % (eschema, entity.eid))
        self.w(u'</%s>'% eschema)


class OWLABOXEView(EntityView):
    '''This view represents a part of the ABOX for a given entity.'''
    
    id = 'owlabox'
    title = _('owlabox')
    templatable =False
    accepts = ('Any',)
    content_type = 'application/xml' # 'text/xml'
    
    def call(self, writeprefix=True):

        skipmeta = int(self.req.form.get('skipmeta', True))
        if writeprefix:
            self.w(OWL_OPENING_ROOT % (self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name, self.schema.name))
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0, skiprels=('is', 'is_instance_of', 'identity',
                                       'owned_by', 'created_by'),
                             skipmeta=skipmeta)
        if writeprefix:
            self.w(OWL_CLOSING_ROOT)
        

    def cell_call(self, row, col, skiprels=(), skipmeta=True):
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
            attr = getattr(entity, aname)
            if attr is not None:
                self.w(u'<%s>%s</%s>' % (aname, html_escape(unicode(attr)), aname))
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

