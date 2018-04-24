# copyright 2018 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""Tests for the entity edition"""

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.edition import EditedEntity


class EditedEntityTC(CubicWebTC):
    """
    Test cases for EditedEntity
    """

    def test_clone_cache_reset(self):
        """
        Tests that when an EditedEntity is cloned the caches are reset in the cloned instance
        :return: Nothing
        """
        # Create an entity, create the EditedEntity and clone it
        with self.admin_access.cnx() as cnx:
            affaire = cnx.create_entity("Affaire", sujet=u"toto")
            ee = EditedEntity(affaire)
            ee.entity.cw_adapt_to("IWorkflowable")
            self.assertTrue(ee.entity._cw_related_cache)
            self.assertTrue(ee.entity._cw_adapters_cache)
            the_clone = ee.clone()
            self.assertFalse(the_clone.entity._cw_related_cache)
            self.assertFalse(the_clone.entity._cw_adapters_cache)
            cnx.rollback()
        # Check the attributes
        with self.admin_access.cnx() as cnx:
            # Assume a different connection set on the entity
            self.assertNotEqual(the_clone.entity._cw, cnx)
            # Use the new connection
            the_clone.entity._cw = cnx
            self.assertEqual("toto", the_clone.entity.sujet)


if __name__ == '__main__':
    import unittest
    unittest.main()
