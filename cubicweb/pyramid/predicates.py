# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# copyright 2014-2016 UNLISH S.A.S. (Montpellier, FRANCE), all rights reserved.
#
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

"""Contains predicates used in Pyramid views.
"""


class MatchIsETypePredicate(object):
    """A predicate that match if a given etype exist in schema.
    """
    def __init__(self, matchname, config):
        self.matchname = matchname

    def text(self):
        return 'match_is_etype = %s' % self.matchname

    phash = text

    def __call__(self, info, request):
        return info['match'][self.matchname].lower() in \
            request.registry['cubicweb.registry'].case_insensitive_etypes


def includeme(config):
    config.add_route_predicate('match_is_etype', MatchIsETypePredicate)
