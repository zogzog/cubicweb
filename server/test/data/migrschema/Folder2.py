"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

class Folder2(MetaUserEntityType):
    """folders are used to classify entities. They may be defined as a tree.
    When you include the Folder entity, all application specific entities
    may then be classified using the "filed_under" relation.
    """
    name = String(required=True, indexed=True, internationalizable=True,
                  constraints=[UniqueConstraint(), SizeConstraint(64)])
    description = RichString(fulltextindexed=True)

    filed_under2 = BothWayRelation(
        SubjectRelation('Folder2', description=_("parent folder")),
        ObjectRelation('*'),
        )


class filed_under2(MetaUserRelationType):
    """indicates that an entity is classified under a folder"""
    # is_about has been renamed into filed_under
    #//* is_about Folder
    #* filed_under Folder

