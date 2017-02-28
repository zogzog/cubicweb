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

"""Various tools.

.. warning::

    This module should be considered as internal implementation details. Use
    with caution, as the API may change without notice.
"""

from repoze.lru import lru_cache


def clone_user(repo, user):
    """Clone a CWUser instance.

    .. warning::

        The returned clone is detached from any cnx.
        Before using it in any way, it should be attached to a cnx that has not
        this user already loaded.
    """
    CWUser = repo.vreg['etypes'].etype_class('CWUser')
    clone = CWUser(
        None,
        rset=user.cw_rset.copy(),
        row=user.cw_row,
        col=user.cw_col)
    clone.cw_attr_cache = dict(user.cw_attr_cache)
    return clone


def cnx_attach_entity(cnx, entity):
    """Attach an entity to a cnx."""
    entity._cw = cnx
    if entity.cw_rset:
        entity.cw_rset.req = cnx


@lru_cache(10)
def cached_build_user(repo, eid):
    """Cached version of
    :meth:`cubicweb.server.repository.Repository._build_user`
    """
    with repo.internal_cnx() as cnx:
        user = repo._build_user(cnx, eid)
        lang = user.prefered_language()
        user.cw_clear_relation_cache()
        return clone_user(repo, user), lang
