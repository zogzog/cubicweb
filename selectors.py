# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from warnings import warn

from six import string_types

from logilab.common.deprecation import deprecated, class_renamed

from cubicweb.predicates import *


warn('[3.15] cubicweb.selectors renamed into cubicweb.predicates',
     DeprecationWarning, stacklevel=2)

# XXX pre 3.15 bw compat
from cubicweb.appobject import (objectify_selector, traced_selection,
                                lltrace, yes)

ExpectedValueSelector = class_renamed('ExpectedValueSelector',
                                      ExpectedValuePredicate)
EClassSelector = class_renamed('EClassSelector', EClassPredicate)
EntitySelector = class_renamed('EntitySelector', EntityPredicate)


class on_transition(is_in_state):
    """Return 1 if entity is in one of the transitions given as argument list

    Especially useful to match passed transition to enable notifications when
    your workflow allows several transition to the same states.

    Note that if workflow `change_state` adapter method is used, this predicate
    will not be triggered.

    You should use this instead of your own :class:`score_entity` predicate to
    avoid some gotchas:

    * possible views gives a fake entity with no state
    * you must use the latest tr info thru the workflow adapter for repository
      side checking of the current state

    In debug mode, this predicate can raise:
    :raises: :exc:`ValueError` for unknown transition names
        (etype workflow only not checked in custom workflow)

    :rtype: int
    """
    @deprecated('[3.12] on_transition is deprecated, you should rather use '
                'on_fire_transition(etype, trname)')
    def __init__(self, *expected):
        super(on_transition, self).__init__(*expected)

    def _score(self, adapted):
        trinfo = adapted.latest_trinfo()
        if trinfo and trinfo.by_transition:
            return trinfo.by_transition[0].name in self.expected

    def _validate(self, adapted):
        wf = adapted.current_workflow
        valid = [n.name for n in wf.reverse_transition_of]
        unknown = sorted(self.expected.difference(valid))
        if unknown:
            raise ValueError("%s: unknown transition(s): %s"
                             % (wf.name, ",".join(unknown)))


entity_implements = class_renamed('entity_implements', is_instance)

class _but_etype(EntityPredicate):
    """accept if the given entity types are not found in the result set.

    See `EntityPredicate` documentation for behaviour when row is not specified.

    :param *etypes: entity types (`string_types`) which should be refused
    """
    def __init__(self, *etypes):
        super(_but_etype, self).__init__()
        self.but_etypes = etypes

    def score(self, req, rset, row, col):
        if rset.description[row][col] in self.but_etypes:
            return 0
        return 1

but_etype = class_renamed('but_etype', _but_etype, 'use ~is_instance(*etypes) instead')

# XXX deprecated the one_* variants of predicates below w/ multi_xxx(nb=1)?
#     take care at the implementation though (looking for the 'row' argument's
#     value)
two_lines_rset = class_renamed('two_lines_rset', multi_lines_rset)
two_cols_rset = class_renamed('two_cols_rset', multi_columns_rset)
two_etypes_rset = class_renamed('two_etypes_rset', multi_etypes_rset)
