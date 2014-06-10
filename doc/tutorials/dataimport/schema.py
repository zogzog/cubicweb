# -*- coding: utf-8 -*-
# copyright 2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.

"""cubicweb-diseasome schema"""

from yams.buildobjs import EntityType, SubjectRelation, String, Int


class Disease(EntityType):
    """Disease entity definition.

    A Disease entity is characterized by several attributes which are 
    defined by URIs:

    - a name, which we define as a CubicWeb / Yams String object
    - a label, also defined as a Yams String
    - a class degree, defined as a Yams Int (that is, an integer)
    - a degree, also defined as a Yams Int
    - size, also defined as an Int
    - classes, defined as a set containing zero, one or several objects 
      identified by their URIs, that is, objects of type ``ExternalUri``
    - subtype_of, defined as a set containing zero, one or several
      objects of type ``Disease``
    - associated_genes, defined as a set containing zero, one or several
      objects of type ``Gene``, that is, of genes associated to the
      disease
    - possible_drugs, defined as a set containing zero, one or several
      objects, identified by their URIs, that is, of type ``ExternalUri``
    - omim and omim_page are identifiers in the OMIM (Online Mendelian
      Inheritance in Man) database, which contains an inventory of "human
      genes and genetic phenotypes" 
      (see http://http://www.ncbi.nlm.nih.gov/omim). Given that a disease
      only has unique omim and omim_page identifiers, when it has them,
      these attributes have been defined through relations such that
      for each disease there is at most one omim and one omim_page. 
      Each such identifier is defined through a URI, that is, through
      an ``ExternalUri`` entity.
      That is, these relations are of cardinality "?*". For optimization
      purposes, one might be tempted to defined them as inlined, by setting
      the ``inlined`` keyword argument to ``True``.
    - chromosomal_location is also defined through a relation of 
      cardinality "?*", since any disease has at most one chromosomal
      location associated to it.
    - same_as is also defined through a URI, and hence through a
      relation having ``ExternalUri`` entities as objects.

    For more information on this data set and the data set itself, 
    please consult http://datahub.io/dataset/fu-berlin-diseasome.
    """
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/name
    name = String(maxsize=256, fulltextindexed=True)
    # Corresponds to http://www.w3.org/2000/01/rdf-schema#label
    label = String(maxsize=512, fulltextindexed=True)
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/classDegree
    class_degree = Int()
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/degree
    degree = Int()
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/size
    size = Int()
    #Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/class
    classes = SubjectRelation('ExternalUri', cardinality='**')
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/diseaseSubtypeOf
    subtype_of = SubjectRelation('Disease', cardinality='**')
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/associatedGene
    associated_genes = SubjectRelation('Gene', cardinality='**')
    #Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/possibleDrug
    possible_drugs = SubjectRelation('ExternalUri', cardinality='**')
    #Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/omim
    omim = SubjectRelation('ExternalUri', cardinality='?*', inlined=True)
    #Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/omimPage
    omim_page = SubjectRelation('ExternalUri', cardinality='?*', inlined=True)
    #Corresponds to 'http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/chromosomalLocation'
    chromosomal_location = SubjectRelation('ExternalUri', cardinality='?*',
                                           inlined=True)
    #Corresponds to http://www.w3.org/2002/07/owl#sameAs
    same_as = SubjectRelation('ExternalUri', cardinality='**')


class Gene(EntityType):
    """Gene entity defintion.

    A gene is characterized by the following attributes:

    - label, defined through a Yams String.
    - bio2rdf_symbol, also defined as a Yams String, since it is 
      just an identifier.
    - gene_id is a URI identifying a gene, hence it is defined
      as a relation with an ``ExternalUri`` object.
    - a pair of unique identifiers in the HUGO Gene Nomenclature
      Committee (http://http://www.genenames.org/). They are defined
      as ``ExternalUri`` entities as well.
    - same_as is also defined through a URI, and hence through a
      relation having ``ExternalUri`` entities as objects.
    """
    # Corresponds to http://www.w3.org/2000/01/rdf-schema#label
    label = String(maxsize=512, fulltextindexed=True)
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/geneId
    gene_id = SubjectRelation('ExternalUri', cardinality='**')
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/hgncId
    hgnc_id = SubjectRelation('ExternalUri', cardinality='**')
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/hgncIdPage
    hgnc_page = SubjectRelation('ExternalUri', cardinality='**')
    # Corresponds to http://www4.wiwiss.fu-berlin.de/diseasome/resource/
    # diseasome/bio2rdfSymbol
    bio2rdf_symbol = String(maxsize=64, fulltextindexed=True)
    #Corresponds to http://www.w3.org/2002/07/owl#sameAs
    same_as = SubjectRelation('ExternalUri', cardinality='**')
