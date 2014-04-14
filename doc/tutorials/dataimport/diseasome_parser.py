# -*- coding: utf-8 -*-

"""
Diseasome data import module.
Its interface is the ``entities_from_rdf`` function.
"""

import re
RE_RELS = re.compile(r'^<(.*?)>\s<(.*?)>\s<(.*?)>\s*\.')
RE_ATTS = re.compile(r'^<(.*?)>\s<(.*?)>\s"(.*)"(\^\^<(.*?)>|)\s*\.')

MAPPING_ATTS = {'bio2rdfSymbol': 'bio2rdf_symbol',
                'label': 'label',
                'name': 'name',
                'classDegree': 'class_degree',
                'degree': 'degree',
                'size': 'size'}

MAPPING_RELS = {'geneId': 'gene_id',
                'hgncId': 'hgnc_id', 
                'hgncIdPage': 'hgnc_page', 
                'sameAs': 'same_as', 
                'class': 'classes', 
                'diseaseSubtypeOf': 'subtype_of', 
                'associatedGene': 'associated_genes', 
                'possibleDrug': 'possible_drugs',
                'type': 'types',
                'omim': 'omim', 
                'omimPage': 'omim_page', 
                'chromosomalLocation': 'chromosomal_location'}

def _retrieve_reltype(uri):
    """
    Retrieve a relation type from a URI.

    Internal function which takes a URI containing a relation type as input
    and returns the name of the relation.
    If no URI string is given, then the function returns None.
    """
    if uri:
        return uri.rsplit('/', 1)[-1].rsplit('#', 1)[-1]

def _retrieve_etype(tri_uri):
    """
    Retrieve entity type from a triple of URIs.

    Internal function whith takes a tuple of three URIs as input
    and returns the type of the entity, as obtained from the
    first member of the tuple.
    """
    if tri_uri:
        return tri_uri.split('> <')[0].rsplit('/', 2)[-2].rstrip('s')

def _retrieve_structure(filename, etypes):
    """
    Retrieve a (subject, relation, object) tuples iterator from a file.

    Internal function which takes as input a file name and a tuple of 
    entity types, and returns an iterator of (subject, relation, object)
    tuples.
    """
    with open(filename) as fil:
        for line in fil:
            if _retrieve_etype(line) not in etypes:
                continue
            match = RE_RELS.match(line)
            if not match:
                match = RE_ATTS.match(line)
            subj = match.group(1)
            relation = _retrieve_reltype(match.group(2))
            obj = match.group(3)
            yield subj, relation, obj

def entities_from_rdf(filename, etypes):
    """
    Return entities from an RDF file.

    Module interface function which takes as input a file name and
    a tuple of entity types, and returns an iterator on the 
    attributes and relations of each entity. The attributes
    and relations are retrieved as dictionaries.
    
    >>> for entities, relations in entities_from_rdf('data_file', 
                                                     ('type_1', 'type_2')):
        ...
    """
    entities = {}
    for subj, rel, obj in _retrieve_structure(filename, etypes):
        entities.setdefault(subj, {})
        entities[subj].setdefault('attributes', {})
        entities[subj].setdefault('relations', {})
        entities[subj]['attributes'].setdefault('cwuri', unicode(subj))
        if rel in MAPPING_ATTS:
            entities[subj]['attributes'].setdefault(MAPPING_ATTS[rel], 
                                                    unicode(obj))
        if rel in MAPPING_RELS:
            entities[subj]['relations'].setdefault(MAPPING_RELS[rel], set())
            entities[subj]['relations'][MAPPING_RELS[rel]].add(unicode(obj))
    return ((ent.get('attributes'), ent.get('relations')) 
            for ent in entities.itervalues())
