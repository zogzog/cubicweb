from yams.buildobjs import EntityType, String, SubjectRelation, RelationType


class Tag(EntityType):
    """tags are used by users to mark entities.
    When you include the Tag entity, all application specific entities
    may then be tagged using the "tags" relation.
    """
    name = String(required=True, fulltextindexed=True, unique=True,
                  maxsize=128)
    # when using this component, add the Tag tag X relation for each type that
    # should be taggeable
    tags = SubjectRelation('Tag', description="tagged objects")


class tags(RelationType):
    """indicates that an entity is classified by a given tag"""
