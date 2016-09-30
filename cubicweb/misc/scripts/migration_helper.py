# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""Helper functions for migrations that aren't reliable enough or too dangerous
to be available in the standard migration environment
"""
from __future__ import print_function



def drop_entity_types_fast(*etypes, **kwargs):
    """drop an entity type bypassing all hooks

    here be dragons.
    """
    # XXX cascade deletion through composite relations?

    for etype in etypes:

        if etype not in schema:
            print('%s does not exist' % etype)
            continue
        etype = schema[etype]

        # ignore attributes and inlined rels since they'll be dropped anyway
        srels = [x.type for x in etype.subject_relations() if x.eid and not (x.final or x.inlined)]

        orels = [x.type for x in etype.object_relations() if x.eid and not x.inlined]
        inlined_rels = [x for x in etype.object_relations() if x.eid and x.inlined]

        # eids to be deleted could be listed in some other entity tables through inlined relations
        for rtype in inlined_rels:
            for subjtype in rtype.subjects(etype):
                if subjtype in etypes:
                    continue
                sql('UPDATE cw_%(stype)s SET cw_%(rtype)s = NULL '
                    'WHERE cw_%(rtype)s IN (SELECT eid FROM entities WHERE type = %%s)' %
                    {'stype': subjtype.type, 'rtype': rtype.type},
                    (etype.type,))

        for rel in srels:
            if all(subj in etypes for subj in rel.subjects()) or all(obj in etypes for obj in rel.objects()):
                sql('DELETE FROM %s_relation' % rel.type)
            else:
                sql('DELETE FROM %s_relation WHERE eid_from IN (SELECT eid FROM entities WHERE type = %%s)' % rel.type, (etype.type,))
        for rel in orels:
            if all(subj in etypes for subj in rel.subjects()) or all(obj in etypes for obj in rel.objects()):
                sql('DELETE FROM %s_relation' % rel.type)
            else:
                sql('DELETE FROM %s_relation WHERE eid_to IN (SELECT eid FROM entities WHERE type = %%s)' % rel, (etype.type,))

        sql('DELETE FROM appears WHERE uid IN (SELECT eid FROM entities WHERE type = %s)', (etype.type,))
        sql('DELETE FROM cw_%s' % etype.type)
        sql('DELETE FROM entities WHERE type = %s', (etype.type,))

    for etype in etypes:
        drop_entity_type(etype, **kwargs)
