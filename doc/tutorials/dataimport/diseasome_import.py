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

"""This module imports the Diseasome data into a CubicWeb instance.
"""

# Python imports
import sys
import argparse

# Logilab import, for timing
from logilab.common.decorators import timed

# CubicWeb imports
import cubicweb.dataimport as cwdi
from cubes.dataio import dataimport as mcwdi

# Diseasome parser import
import diseasome_parser as parser

def _is_of_class(instance, class_name):
    """Helper function to determine whether an instance is
    of a specified class or not.
    Returns a True if this is the case and False otherwise.
    """
    if instance.__class__.__name__ == class_name:
        return True
    else:
        return False

@timed
def diseasome_import(session, file_name, store):
    """Main function for importing Diseasome data.

    It uses the Diseasome data parser to get the contents of the
    data from a file, then uses a store for importing the data
    into a CubicWeb instance.

    >>> diseasome_import(session, 'file_name', Store)

    """
    exturis = dict(session.execute('Any U, X WHERE X is ExternalUri, X uri U'))
    uri_to_eid = {}
    uri_to_etype = {}
    all_relations = {}
    etypes = {('http://www4.wiwiss.fu-berlin.de/'
               'diseasome/resource/diseasome/genes'): 'Gene',
              ('http://www4.wiwiss.fu-berlin.de/'
               'diseasome/resource/diseasome/diseases'): 'Disease'}
    # Read the parsed data
    for entity, relations in parser.entities_from_rdf(file_name, 
                                                      ('gene', 'disease')):
        uri = entity.get('cwuri', None)
        types = list(relations.get('types', []))
        if not types:
            continue
        etype = etypes.get(types[0])
        if not etype:
            sys.stderr.write('Entity type %s not recognized.', types[0])
            sys.stderr.flush()
        if _is_of_class(store, 'MassiveObjectStore'):
            for relation in (set(relations).intersection(('classes', 
                            'possible_drugs', 'omim', 'omim_page', 
                            'chromosomal_location', 'same_as', 'gene_id',
                            'hgnc_id', 'hgnc_page'))):
                store.init_rtype_table(etype, relation, 'ExternalUri')
            for relation in set(relations).intersection(('subtype_of',)):
                store.init_rtype_table(etype, relation, 'Disease')
            for relation in set(relations).intersection(('associated_genes',)):
                store.init_rtype_table(etype, relation, 'Gene')
        # Create the entities
        ent = store.create_entity(etype, **entity)
        if not _is_of_class(store, 'MassiveObjectStore'):
            uri_to_eid[uri] = ent.eid
            uri_to_etype[uri] = ent.cw_etype
        else:
            uri_to_eid[uri] = uri
            uri_to_etype[uri] = etype
        # Store relations for after
        all_relations[uri] = relations
    # Perform a first commit, of the entities
    store.flush()
    kwargs = {}
    for uri, relations in all_relations.items():
        from_eid = uri_to_eid.get(uri)
        # ``subjtype`` should be initialized if ``SQLGenObjectStore`` is used
        # and there are inlined relations in the schema.
        # If ``subjtype`` is not given, while ``SQLGenObjectStore`` is used
        # and there are inlined relations in the schema, the store
        # tries to infer the type of the subject, but this does not always 
        # work, e.g. when there are several object types for the relation.
        # ``subjtype`` is ignored for other stores, or if there are no
        # inlined relations in the schema.
        kwargs['subjtype'] = uri_to_etype.get(uri)
        if not from_eid:
            continue
        for rtype, rels in relations.items():
            if rtype in ('classes', 'possible_drugs', 'omim', 'omim_page',
                         'chromosomal_location', 'same_as', 'gene_id',
                         'hgnc_id', 'hgnc_page'):
                for rel in list(rels):
                    if rel not in exturis:
                        # Create the "ExternalUri" entities, which are the
                        # objects of the relations
                        extu = store.create_entity('ExternalUri', uri=rel)
                        if not _is_of_class(store, 'MassiveObjectStore'):
                            rel_eid = extu.eid
                        else:
                            # For the "MassiveObjectStore", the EIDs are 
                            # in fact the URIs.
                            rel_eid = rel
                        exturis[rel] = rel_eid
                    else:
                        rel_eid = exturis[rel]
                    # Create the relations that have "ExternalUri"s as objects
                    if not _is_of_class(store, 'MassiveObjectStore'):
                        store.relate(from_eid, rtype, rel_eid, **kwargs)
                    else:
                        store.relate_by_iid(from_eid, rtype, rel_eid)
            elif rtype in ('subtype_of', 'associated_genes'):
                for rel in list(rels):
                    to_eid = uri_to_eid.get(rel)
                    if to_eid:
                        # Create relations that have objects of other type 
                        # than "ExternalUri"
                        if not _is_of_class(store, 'MassiveObjectStore'):
                            store.relate(from_eid, rtype, to_eid, **kwargs)
                        else:
                            store.relate_by_iid(from_eid, rtype, to_eid)
                    else:
                        sys.stderr.write('Missing entity with URI %s '
                                         'for relation %s' % (rel, rtype))
                        sys.stderr.flush()
    # Perform a second commit, of the "ExternalUri" entities.
    # when the stores in the CubicWeb ``dataimport`` module are used,
    # relations are also committed.
    store.flush()
    # If the ``MassiveObjectStore`` is used, then entity and relation metadata
    # are pushed as well. By metadata we mean information on the creation
    # time and author.
    if _is_of_class(store, 'MassiveObjectStore'):
        for relation in ('classes', 'possible_drugs', 'omim', 'omim_page', 
                         'chromosomal_location', 'same_as'):
            # Afterwards, relations are actually created in the database.
            store.convert_relations('Disease', relation, 'ExternalUri',
                                    'cwuri', 'uri')
        store.convert_relations('Disease', 'subtype_of', 'Disease', 
                                'cwuri', 'cwuri')
        store.convert_relations('Disease', 'associated_genes', 'Gene', 
                                'cwuri', 'cwuri')
        for relation in ('gene_id', 'hgnc_id', 'hgnc_page', 'same_as'):
            store.convert_relations('Gene', relation, 'ExternalUri', 
                                    'cwuri', 'uri')
        # Clean up temporary tables in the database
        store.cleanup()

if __name__ == '__main__':
    # Change sys.argv so that ``cubicweb-ctl shell`` can work out the options
    # we give to our ``diseasome_import.py`` script.
    sys.argv = [arg for 
                arg in sys.argv[sys.argv.index("--") - 1:] if arg != "--"]
    PARSER = argparse.ArgumentParser(description="Import Diseasome data")
    PARSER.add_argument("-df", "--datafile", type=str,
                        help="RDF data file name")
    PARSER.add_argument("-st", "--store", type=str,
                        default="RQLObjectStore",
                        help="data import store")
    ARGS = PARSER.parse_args()
    if ARGS.datafile:
        FILENAME = ARGS.datafile
        if ARGS.store in (st + "ObjectStore" for 
                          st in ("RQL", "NoHookRQL", "SQLGen")):
            IMPORT_STORE = getattr(cwdi, ARGS.store)(session)
        elif ARGS.store == "MassiveObjectStore":
            IMPORT_STORE = mcwdi.MassiveObjectStore(session)
        else:
            sys.exit("Import store unknown")
        diseasome_import(session, FILENAME, IMPORT_STORE)
    else:
        sys.exit("Data file not found or not specified")
