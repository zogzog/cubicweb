"""unittests for schema2dot"""

import os

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.compat import set
from cubicweb.devtools.testlib import WebTest

from lxml import etree
from StringIO import StringIO

       
class OWLTC(WebTest):
    
    def test_schema2owl(self):

        parser = etree.XMLParser(dtd_validation=True)

        owl= StringIO('''<xsd:schema 
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 targetNamespace="http://www.w3.org/2002/07/owl#"
 elementFormDefault="qualified" attributeFormDefault="unqualified">

<xsd:import namespace="http://www.w3.org/XML/1998/namespace" schemaLocation="http://www.w3.org/2001/xml.xsd"/>

<!-- The ontology -->
  
<xsd:element name="Import">
  <xsd:complexType>
    <xsd:simpleContent>
      <xsd:extension base="xsd:anyURI">
        <xsd:attributeGroup ref="xml:specialAttrs"/>
      </xsd:extension>
    </xsd:simpleContent>
  </xsd:complexType>
</xsd:element>

<xsd:element name="Ontology">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:element ref="owl:Import" minOccurs="0" maxOccurs="unbounded"/>
      <xsd:group ref="owl:ontologyAnnotations"/>
      <xsd:group ref="owl:Axiom" minOccurs="0" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attribute name="ontologyIRI" type="xsd:anyURI" use="optional"/>
    <xsd:attribute name="versionIRI" type="xsd:anyURI" use="optional"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Entities, anonymous individuals, and literals -->

<xsd:group name="Entity">
  <xsd:choice>
    <xsd:element ref="owl:Class"/>
    <xsd:element ref="owl:Datatype"/>
    <xsd:element ref="owl:ObjectProperty"/>
    <xsd:element ref="owl:DataProperty"/>
    <xsd:element ref="owl:AnnotationProperty"/>
    <xsd:element ref="owl:NamedIndividual"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="Class">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="Datatype">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>
 
<xsd:element name="ObjectProperty">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataProperty">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="AnnotationProperty">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:group name="Individual">
  <xsd:choice>
    <xsd:element ref="owl:NamedIndividual"/>
    <xsd:element ref="owl:AnonymousIndividual"/>
  </xsd:choice>
</xsd:group>
  
<xsd:element name="NamedIndividual">
  <xsd:complexType>
    <xsd:attribute name="IRI" type="xsd:anyURI" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="AnonymousIndividual">
  <xsd:complexType>
    <xsd:attribute name="nodeID" type="xsd:NCName" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="Literal">
 <xsd:complexType>
   <xsd:simpleContent>
     <xsd:extension base="xsd:string">
       <xsd:attribute name="datatypeIRI" type="xsd:anyURI"/>
       <xsd:attributeGroup ref="xml:specialAttrs"/>
     </xsd:extension>
   </xsd:simpleContent>
 </xsd:complexType>
</xsd:element>

<!-- Declarations -->

<xsd:element name="Declaration">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:Entity"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>
  
<!-- Object property expressions -->

<xsd:group name="ObjectPropertyExpression">
  <xsd:choice>
    <xsd:element ref="owl:ObjectProperty"/>
    <xsd:element ref="owl:InverseObjectProperty"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="InverseObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:element ref="owl:ObjectProperty"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Data property expressions -->

<xsd:group name="DataPropertyExpression">
  <xsd:sequence>
    <xsd:element ref="owl:DataProperty"/>
  </xsd:sequence>
</xsd:group>

<!-- Data ranges -->

<xsd:group name="DataRange">
  <xsd:choice>
    <xsd:element ref="owl:Datatype"/>
    <xsd:element ref="owl:DataIntersectionOf"/>
    <xsd:element ref="owl:DataUnionOf"/>
    <xsd:element ref="owl:DataComplementOf"/>
    <xsd:element ref="owl:DataOneOf"/>
    <xsd:element ref="owl:DatatypeRestriction"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="DataIntersectionOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataRange" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataUnionOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataRange" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataComplementOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataRange"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataOneOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:element ref="owl:Literal" minOccurs="1" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DatatypeRestriction">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:element ref="owl:Datatype"/>
      <xsd:element name="FacetRestriction" minOccurs="1" maxOccurs="unbounded">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element ref="owl:Literal"/>
          </xsd:sequence>
          <xsd:attribute name="facet" type="xsd:anyURI" use="required"/>
        </xsd:complexType>
      </xsd:element>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Class expressions -->

<xsd:group name="ClassExpression">
  <xsd:choice>
    <xsd:element ref="owl:Class"/>
    <xsd:element ref="owl:ObjectIntersectionOf"/>
    <xsd:element ref="owl:ObjectUnionOf"/>
    <xsd:element ref="owl:ObjectComplementOf"/>
    <xsd:element ref="owl:ObjectOneOf"/>
    <xsd:element ref="owl:ObjectSomeValuesFrom"/>
    <xsd:element ref="owl:ObjectAllValuesFrom"/>
    <xsd:element ref="owl:ObjectHasValue"/>
    <xsd:element ref="owl:ObjectHasSelf"/>
    <xsd:element ref="owl:ObjectMinCardinality"/>
    <xsd:element ref="owl:ObjectMaxCardinality"/>
    <xsd:element ref="owl:ObjectExactCardinality"/>
    <xsd:element ref="owl:DataSomeValuesFrom"/>
    <xsd:element ref="owl:DataAllValuesFrom"/>
    <xsd:element ref="owl:DataHasValue"/>
    <xsd:element ref="owl:DataMinCardinality"/>
    <xsd:element ref="owl:DataMaxCardinality"/>
    <xsd:element ref="owl:DataExactCardinality"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="ObjectIntersectionOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ClassExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectUnionOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ClassExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectComplementOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectOneOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:Individual" minOccurs="1" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectSomeValuesFrom">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectAllValuesFrom">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectHasValue">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:Individual"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectHasSelf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectMinCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectMaxCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectExactCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataSomeValuesFrom">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression" minOccurs="1" maxOccurs="unbounded"/>
      <xsd:group ref="owl:DataRange"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataAllValuesFrom">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression" minOccurs="1" maxOccurs="unbounded"/>
      <xsd:group ref="owl:DataRange"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataHasValue">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:element ref="owl:Literal"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataMinCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:DataRange" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataMaxCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:DataRange" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataExactCardinality">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:DataRange" minOccurs="0" maxOccurs="1"/>
    </xsd:sequence>
    <xsd:attribute name="cardinality" type="xsd:nonNegativeInteger" use="required"/>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Axioms -->

<xsd:group name="Axiom">
  <xsd:choice>
    <xsd:element ref="owl:Declaration"/>
    <xsd:group ref="owl:ClassAxiom"/>
    <xsd:group ref="owl:ObjectPropertyAxiom"/>
    <xsd:group ref="owl:DataPropertyAxiom"/>
    <xsd:element ref="owl:HasKey"/>
    <xsd:group ref="owl:Assertion"/>
    <xsd:group ref="owl:AnnotationAxiom"/>
  </xsd:choice>
</xsd:group>

<!-- Class expression axioms -->

<xsd:group name="ClassAxiom">
  <xsd:choice>
    <xsd:element ref="owl:SubClassOf"/>
    <xsd:element ref="owl:EquivalentClasses"/>
    <xsd:element ref="owl:DisjointClasses"/>
    <xsd:element ref="owl:DisjointUnion"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="SubClassOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ClassExpression"/> <!-- This is the subexpression -->
      <xsd:group ref="owl:ClassExpression"/> <!-- This is the superexpression -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="EquivalentClasses">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DisjointClasses">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DisjointUnion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:element ref="owl:Class"/>
      <xsd:group ref="owl:ClassExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Object property axioms -->

<xsd:group name="ObjectPropertyAxiom">
  <xsd:choice>
    <xsd:element ref="owl:SubObjectPropertyOf"/>
    <xsd:element ref="owl:EquivalentObjectProperties"/>
    <xsd:element ref="owl:DisjointObjectProperties"/>
    <xsd:element ref="owl:InverseObjectProperties"/>
    <xsd:element ref="owl:ObjectPropertyDomain"/>
    <xsd:element ref="owl:ObjectPropertyRange"/>
    <xsd:element ref="owl:FunctionalObjectProperty"/>
    <xsd:element ref="owl:InverseFunctionalObjectProperty"/>
    <xsd:element ref="owl:ReflexiveObjectProperty"/>
    <xsd:element ref="owl:IrreflexiveObjectProperty"/>
    <xsd:element ref="owl:SymmetricObjectProperty"/>
    <xsd:element ref="owl:AsymmetricObjectProperty"/>
    <xsd:element ref="owl:TransitiveObjectProperty"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="SubObjectPropertyOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:choice> <!-- This is the subproperty expression or the property chain -->
        <xsd:group ref="owl:ObjectPropertyExpression"/>
        <xsd:element name="PropertyChain">
          <xsd:complexType>
            <xsd:sequence>
              <xsd:group ref="owl:ObjectPropertyExpression" minOccurs="2" maxOccurs="unbounded"/>
            </xsd:sequence>
            <xsd:attributeGroup ref="xml:specialAttrs"/>
          </xsd:complexType>
        </xsd:element>
      </xsd:choice>
      <xsd:group ref="owl:ObjectPropertyExpression"/> <!-- This is the superproperty expression -->  
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="EquivalentObjectProperties">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DisjointObjectProperties">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectPropertyDomain">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectPropertyRange">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="InverseObjectProperties">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression" minOccurs="2" maxOccurs="2"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="FunctionalObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="InverseFunctionalObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ReflexiveObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="IrreflexiveObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="SymmetricObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="AsymmetricObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>
 
<xsd:element name="TransitiveObjectProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Data property axioms -->

<xsd:group name="DataPropertyAxiom">
  <xsd:choice>
    <xsd:element ref="owl:SubDataPropertyOf"/>
    <xsd:element ref="owl:EquivalentDataProperties"/>
    <xsd:element ref="owl:DisjointDataProperties"/>
    <xsd:element ref="owl:DataPropertyDomain"/>
    <xsd:element ref="owl:DataPropertyRange"/>
    <xsd:element ref="owl:FunctionalDataProperty"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="SubDataPropertyOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/> <!-- This is the subproperty expression -->
      <xsd:group ref="owl:DataPropertyExpression"/> <!-- This is the superproperty expression -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="EquivalentDataProperties">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DisjointDataProperties">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataPropertyDomain">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:ClassExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataPropertyRange">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:DataRange"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="FunctionalDataProperty">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Key axioms -->

<xsd:element name="HasKey">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ClassExpression"/>
      <xsd:choice minOccurs="1" maxOccurs="unbounded">
        <xsd:group ref="owl:ObjectPropertyExpression"/>
        <xsd:group ref="owl:DataPropertyExpression"/>
      </xsd:choice>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Assertions -->

<xsd:group name="Assertion">
  <xsd:choice>
    <xsd:element ref="owl:SameIndividual"/>
    <xsd:element ref="owl:DifferentIndividuals"/>
    <xsd:element ref="owl:ClassAssertion"/>
    <xsd:element ref="owl:ObjectPropertyAssertion"/>
    <xsd:element ref="owl:NegativeObjectPropertyAssertion"/>
    <xsd:element ref="owl:DataPropertyAssertion"/>
    <xsd:element ref="owl:NegativeDataPropertyAssertion"/>
  </xsd:choice>
</xsd:group> 

<xsd:element name="SameIndividual">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:Individual" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DifferentIndividuals">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:Individual" minOccurs="2" maxOccurs="unbounded"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ClassAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ClassExpression"/>
      <xsd:group ref="owl:Individual"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="ObjectPropertyAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:Individual"/> <!-- This is the source invididual  -->
      <xsd:group ref="owl:Individual"/> <!-- This is the target individual -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="NegativeObjectPropertyAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:ObjectPropertyExpression"/>
      <xsd:group ref="owl:Individual"/> <!-- This is the source invididual  -->
      <xsd:group ref="owl:Individual"/> <!-- This is the target individual -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="DataPropertyAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:Individual"/> <!-- This is the source invididual  -->
      <xsd:element ref="owl:Literal"/> <!-- This is the target value -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="NegativeDataPropertyAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:group ref="owl:DataPropertyExpression"/>
      <xsd:group ref="owl:Individual"/> <!-- This is the source invididual  -->
      <xsd:element ref="owl:Literal"/> <!-- This is the target value -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<!-- Annotations  -->

<xsd:element name="IRI">
  <xsd:complexType>
    <xsd:simpleContent>
      <xsd:extension base="xsd:anyURI">
        <xsd:attributeGroup ref="xml:specialAttrs"/>
      </xsd:extension>
    </xsd:simpleContent>
  </xsd:complexType>
</xsd:element>

<xsd:group name="AnnotationSubject">
  <xsd:choice>
    <xsd:element ref="owl:IRI"/>
    <xsd:element ref="owl:AnonymousIndividual"/>
  </xsd:choice>
</xsd:group>

<xsd:group name="AnnotationValue">
  <xsd:choice>
    <xsd:element ref="owl:IRI"/>
    <xsd:element ref="owl:AnonymousIndividual"/>
    <xsd:element ref="owl:Literal"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="Annotation">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:annotationAnnotations"/>
      <xsd:element ref="owl:AnnotationProperty"/>
      <xsd:group ref="owl:AnnotationValue"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:group name="axiomAnnotations">
  <xsd:sequence>
    <xsd:element ref="owl:Annotation" minOccurs="0" maxOccurs="unbounded"/>
  </xsd:sequence>
</xsd:group>

<xsd:group name="ontologyAnnotations">
  <xsd:sequence>
    <xsd:element ref="owl:Annotation" minOccurs="0" maxOccurs="unbounded"/>
  </xsd:sequence>
</xsd:group>

<xsd:group name="annotationAnnotations">
  <xsd:sequence>
    <xsd:element ref="owl:Annotation" minOccurs="0" maxOccurs="unbounded"/>
  </xsd:sequence>
</xsd:group>

<!-- Annotation axioms -->

<xsd:group name="AnnotationAxiom">
  <xsd:choice>
    <xsd:element ref="owl:AnnotationAssertion"/>
    <xsd:element ref="owl:SubAnnotationPropertyOf"/>
    <xsd:element ref="owl:AnnotationPropertyDomain"/>
    <xsd:element ref="owl:AnnotationPropertyRange"/>
  </xsd:choice>
</xsd:group>

<xsd:element name="AnnotationAssertion">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:element ref="owl:AnnotationProperty"/>
      <xsd:group ref="owl:AnnotationSubject"/>
      <xsd:group ref="owl:AnnotationValue"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="SubAnnotationPropertyOf">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:element ref="owl:AnnotationProperty"/> <!-- This is the subproperty -->
      <xsd:element ref="owl:AnnotationProperty"/> <!-- This is the superproperty -->
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="AnnotationPropertyDomain">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:element ref="owl:AnnotationProperty"/>
      <xsd:element ref="owl:IRI"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

<xsd:element name="AnnotationPropertyRange">
  <xsd:complexType>
    <xsd:sequence>
      <xsd:group ref="owl:axiomAnnotations"/>
      <xsd:element ref="owl:AnnotationProperty"/>
      <xsd:element ref="owl:IRI"/>
    </xsd:sequence>
    <xsd:attributeGroup ref="xml:specialAttrs"/>
  </xsd:complexType>
</xsd:element>

</xsd:schema>

''')

        rdf = StringIO('''<xsd:schema
        xmlns:xsd="http://www.w3.org/1999/XMLSchema"
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        targetNamespace="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
      
        <xsd:element name="RDF">
                <xsd:complexType  content="elementOnly" >
                        <xsd:sequence  maxOccurs="*" >
                                <xsd:choice>
                                        <xsd:element ref="rdf:TypedNode"   /><!-- abstract !-->
                                        <xsd:element ref="rdf:Bag" />
                                        <xsd:element ref="rdf:Seq" />
                                        <xsd:element ref="rdf:Alt" />
                                </xsd:choice>
                        </xsd:sequence>
                </xsd:complexType>
        </xsd:element>

        <!-- RDF Typed nodes -->
       <xsd:complexType   name="TypedNodeType" content="elementOnly" >
                <xsd:sequence maxOccurs="*" >
                        <xsd:element ref="rdf:PropertyElt"   /><!--abstract !-->
                </xsd:sequence>
                <xsd:attribute  name="id" minOccurs="0" type="ID"  />
                <xsd:attribute  name="type" minOccurs="0" type="string" />
                <xsd:attribute name="about" minOccurs="0" type="string" />
                <xsd:attribute  name="aboutEach" minOccurs="0" type="string" />
                <xsd:attribute   name="aboutEachPrefix" minOccurs="0" type="string" />
                <xsd:attribute  name="badID" minOccurs="0" type="ID" />
        </xsd:complexType>
        <xsd:element name="TypedNode"  abstract="true"  type="rdf:TypedNodeType" />

        <xsd:element name="Description"
                type="rdf:TypedNodeType" equivClass="rdf:TypedNode" />


        <!-- RDF Property Elements -->
        <xsd:complexType  name="PropertyEltType" >
                <xsd:any minOccurs="0" />
                <xsd:attribute name="id"  minOccurs="0"  type="ID" />
                <xsd:attribute  name="resource" minOccurs="0"  type="string" />
                <xsd:attribute  name="value" minOccurs="0"  type="string" />
                <xsd:attribute  name="badID" minOccurs="0" type="ID"  />
                <xsd:attribute name="parseType"  minOccurs="0" >
                        <xsd:simpleType base="NMTOKEN">
                                 <xsd:enumeration value="Resource"/>
                                 <xsd:enumeration value="Literal" />
                       </xsd:simpleType>
                </xsd:attribute>
                <xsd:anyAttribute  />
        </xsd:complexType>

        <xsd:element name="PropertyElt"  abstract="true" type="rdf:PropertyEltType" />

        <xsd:element   name="subject"   equivClass="rdf:PropertyElt"  />
        <xsd:element name="predicate"   equivClass="rdf:PropertyElt" />
        <xsd:element name="object"  equivClass="rdf:PropertyElt" />
        <xsd:element   name="type"  equivClass="rdf:PropertyElt" />

        <xsd:element name="value">
                <xsd:complexType>
                        <xsd:any />
                        <xsd:anyAttribute />
                </xsd:complexType>
        </xsd:element>


        <!-- RDF Containers -->
        <xsd:complexType name="Container" abstract="true" content="elementOnly" >
                <xsd:sequence maxOccurs="*">
                        <xsd:element name="li">
                                <xsd:complexType>
                                        <xsd:any/>
                                        <xsd:attribute name="id"  minOccurs="0" type="ID" />
                                        <xsd:attribute name="parseType" minOccurs="0" >
                                                <xsd:simpleType base="NMTOKEN">
                                                     <xsd:enumeration value="Resource"/>
                                                     <xsd:enumeration value="Literal" />
                                                </xsd:simpleType>
                                        </xsd:attribute>
                                        <xsd:anyAttribute />
                                </xsd:complexType>
                        </xsd:element>
                </xsd:sequence>
                <xsd:attribute name="id" type="ID" />
                <xsd:anyAttribute />
        </xsd:complexType>

        <xsd:element name="Alt" type="rdf:Container" />
        <xsd:element name="Bag" type="rdf:Container" />
        <xsd:element name="Seq" type="rdf:Container" />

</xsd:schema>

 ''')
        
        
        xmlschema_rdf = etree.parse(rdf)
        xmlschema_owl = etree.parse(owl)
        
        owlschema = etree.XMLSchema(xmlschema_owl)
        valid = StringIO('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE rdf:RDF [
        <!ENTITY owl "http://www.w3.org/2002/07/owl#" >
        <!ENTITY xsd "http://www.w3.org/2001/XMLSchema#" >
        <!ENTITY rdfs "http://www.w3.org/2000/01/rdf-schema#" >
        <!ENTITY rdf "http://www.w3.org/1999/02/22-rdf-syntax-ns#" >
        <!ENTITY inst_jplorg2 "http://logilab.org/owl/ontologies/inst_jplorg2#" >
        
        ]>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#" xmlns:xsd="http://www.w3.org/2001/XMLSchema#" xmlns:owl="http://www.w3.org/2002/07/owl#" xmlns="http://logilab.org/owl/ontologies/inst_jplorg2#" xmlns:inst_jplorg2="http://logilab.org/owl/ontologies/inst_jplorg2#" xml:base="http://logilab.org/owl/ontologies/inst_jplorg2#">

    <owl:Ontology rdf:about="">
        <rdfs:comment>
        inst_jplorg2 Cubicweb OWL Ontology                           
                                        
        </rdfs:comment>
        <!-- classes definition --><owl:Class rdf:ID="Blog"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#interested_in"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#entry_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="BlogEntry"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#entry_of"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#interested_in"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#content_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#content"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Card"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#test_case_for"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#test_case_of"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#documented_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#instance_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#synopsis"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#content_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#content"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#wikiid"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Email"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#sent_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#sender"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#recipients"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#cc"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#parts"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#reply_to"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#cites"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_thread"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#generated_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#generated_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#reply_to"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#cites"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#subject"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#messageid"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#headers"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="EmailThread"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#forked_from"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_thread"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#forked_from"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="ExtProject"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#recommends"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#uses"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#url"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="File"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#documented_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data_encoding"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Image"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#screenshot"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#data_encoding"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="License"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#license_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#shortdesc"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#longdesc_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#longdesc"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#url"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Link"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#url"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#embed"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="MailingList"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#use_email"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#mailinglist_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#sent_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#mlid"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#archive"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#homepage"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Project"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#uses"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#uses"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#recommends"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#recommends"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#documented_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#documented_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#screenshot"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_state"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#filed_under"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#recommends"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#concerns"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#test_case_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#mailinglist_of"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#uses"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#interested_in"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#license_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#version_of"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#wf_info_for"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#summary"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#url"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#vcsurl"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#reporturl"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#downloadurl"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#debian_source_package"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="TestInstance"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#instance_of"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#for_version"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#generate_bug"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_state"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#wf_info_for"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#name"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Ticket"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#see_also"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#concerns"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#appeared_in"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#done_in"/>
                                <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_state"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#attachment"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#identical_to"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#depends_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#depends_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#comments"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#generate_bug"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#wf_info_for"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#test_case_for"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#title"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#type"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#priority"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#load"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#load_left"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#debian_bug_number"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><owl:Class rdf:ID="Version"><rdfs:subClassOf rdf:resource="http://www.w3.org/2002/07/owl#Thing"/>
                                <!-- relations --><rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_basket"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#version_of"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#todo_by"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#in_state"/>
                                <owl:minCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:minCardinality>
                        <owl:maxCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:maxCardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#conflicts"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#depends_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#require_permission"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#done_in"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#tags"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#depends_on"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#for_version"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#wf_info_for"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <rdfs:subClassOf>
                              <owl:Restriction>
                              <owl:onProperty rdf:resource="#appeared_in"/>
                                <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">n</owl:cardinality>
                              </owl:Restriction>
                           </rdfs:subClassOf>
                                <!-- attributes --><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#num"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description_format"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#description"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#starting_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#prevision_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#publication_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#creation_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf><rdfs:subClassOf>
                              <owl:Restriction>
                                  <owl:onProperty rdf:resource="#modification_date"/>
                                  <owl:cardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:cardinality>
                              </owl:Restriction>
                        </rdfs:subClassOf></owl:Class><!-- property definition --><!-- object property --><owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Blog"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="interested_in">
                              <rdfs:domain rdf:resource="#Blog"/>
                              <rdfs:range rdf:resource="#EUser"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="entry_of">
                              <rdfs:domain rdf:resource="#Blog"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="entry_of">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Blog"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="interested_in">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#EUser"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#BlogEntry"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="test_case_for">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="test_case_of">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="documented_by">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="instance_of">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#TestInstance"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Card"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="sent_on">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#MailingList"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="sender">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#EmailAddress"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="recipients">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#EmailAddress"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="cc">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#EmailAddress"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="parts">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#EmailPart"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="reply_to">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="cites">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_thread">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#EmailThread"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="generated_by">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#TrInfo"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="generated_by">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="reply_to">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="cites">
                              <rdfs:domain rdf:resource="#Email"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#EmailThread"/>
                              <rdfs:range rdf:resource="#EmailThread"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="forked_from">
                              <rdfs:domain rdf:resource="#EmailThread"/>
                              <rdfs:range rdf:resource="#EmailThread"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#EmailThread"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_thread">
                              <rdfs:domain rdf:resource="#EmailThread"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="forked_from">
                              <rdfs:domain rdf:resource="#EmailThread"/>
                              <rdfs:range rdf:resource="#EmailThread"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="recommends">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="uses">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#ExtProject"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="documented_by">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#File"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="screenshot">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Image"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#License"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="license_of">
                              <rdfs:domain rdf:resource="#License"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#License"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Link"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#MailingList"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="use_email">
                              <rdfs:domain rdf:resource="#MailingList"/>
                              <rdfs:range rdf:resource="#EmailAddress"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="mailinglist_of">
                              <rdfs:domain rdf:resource="#MailingList"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="sent_on">
                              <rdfs:domain rdf:resource="#MailingList"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#MailingList"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="uses">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="uses">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="recommends">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="recommends">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="documented_by">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="documented_by">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="screenshot">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_state">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#State"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="filed_under">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Folder"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="recommends">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="concerns">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="test_case_of">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="mailinglist_of">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#MailingList"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="uses">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="interested_in">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#EUser"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="license_of">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#License"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="version_of">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="wf_info_for">
                              <rdfs:domain rdf:resource="#Project"/>
                              <rdfs:range rdf:resource="#TrInfo"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="instance_of">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="for_version">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="generate_bug">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_state">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#State"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="wf_info_for">
                              <rdfs:domain rdf:resource="#TestInstance"/>
                              <rdfs:range rdf:resource="#TrInfo"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#ExtProject"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#BlogEntry"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Link"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Email"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="see_also">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="concerns">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="appeared_in">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="done_in">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_state">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#State"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Image"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="attachment">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#File"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="identical_to">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="depends_on">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="depends_on">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="comments">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Comment"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="generate_bug">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#TestInstance"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="wf_info_for">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#TrInfo"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="test_case_for">
                              <rdfs:domain rdf:resource="#Ticket"/>
                              <rdfs:range rdf:resource="#Card"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_basket">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Basket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="version_of">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Project"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="todo_by">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#EUser"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="in_state">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#State"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="conflicts">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="depends_on">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="require_permission">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#EPermission"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="done_in">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="tags">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Tag"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="depends_on">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Version"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="for_version">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#TestInstance"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="wf_info_for">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#TrInfo"/>
                           </owl:ObjectProperty>                   
                             
                                <owl:ObjectProperty rdf:ID="appeared_in">
                              <rdfs:domain rdf:resource="#Version"/>
                              <rdfs:range rdf:resource="#Ticket"/>
                           </owl:ObjectProperty>                   
                             
                                <!-- datatype property --><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#Blog"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Blog"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Blog"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Blog"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#BlogEntry"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="content_format">
                          <rdfs:domain rdf:resource="#BlogEntry"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="content">
                          <rdfs:domain rdf:resource="#BlogEntry"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#BlogEntry"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#BlogEntry"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="synopsis">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="content_format">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="content">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="wikiid">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Card"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="subject">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="date">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="messageid">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="headers">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Email"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#EmailThread"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#EmailThread"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#EmailThread"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="url">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#ExtProject"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:byte"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data_format">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data_encoding">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#File"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:byte"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data_format">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="data_encoding">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Image"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="shortdesc">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="longdesc_format">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="longdesc">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="url">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#License"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="url">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="embed">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:boolean"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Link"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="mlid">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="archive">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="homepage">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#MailingList"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="summary">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="url">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="vcsurl">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="reporturl">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="downloadurl">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="debian_source_package">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Project"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="name">
                          <rdfs:domain rdf:resource="#TestInstance"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#TestInstance"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#TestInstance"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="title">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="type">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="priority">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="load">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:float"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="load_left">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:float"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="debian_bug_number">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:int"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Ticket"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="num">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description_format">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="description">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:string"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="starting_date">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:date"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="prevision_date">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:date"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="publication_date">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:date"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="creation_date">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty><owl:DatatypeProperty rdf:ID="modification_date">
                          <rdfs:domain rdf:resource="#Version"/>
                          <rdfs:range rdf:resource="xsd:dateTime"/>
                       </owl:DatatypeProperty> </owl:Ontology></rdf:RDF> ''')
        doc = etree.parse(valid)
        owlschema.validate(doc)

if __name__ == '__main__':
    unittest_main()

