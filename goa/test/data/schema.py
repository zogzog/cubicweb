

class YamsEntity(EntityType):
    if 'Blog' in defined_types and 'Article' in defined_types:
        ambiguous_relation = SubjectRelation(('Blog', 'Article'))
    if 'Blog' in defined_types:
        inlined_relation = SubjectRelation('Blog', cardinality='?*')

class inlined_relation(RelationType):
    inlined = True

