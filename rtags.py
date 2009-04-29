"""relation tags store

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"


class RelationTags(object):
    """a tag store for full relation definitions :

         (subject type, relation type, object type, tagged)

    allowing to set tags using wildcard (eg '*') as subject type / object type

    This class associates a single tag to each key.
    """

    def __init__(self):
        self._tagdefs = {}

    def __repr__(self):
        return repr(self._tagdefs)

    # dict compat
    def __getitem__(self, key):
        return self.get(*key)
    __contains__ = __getitem__

    def _get_keys(self, rtype, tagged, stype, otype):
        assert tagged in ('subject', 'object'), tagged
        keys = [(rtype, tagged, '*', '*'),
                (rtype, tagged, '*', otype),
                (rtype, tagged, stype, '*'),
                (rtype, tagged, stype, otype)]
        if stype == '*' or otype == '*':
            keys.remove((rtype, tagged, '*', '*'))
            if stype == '*':
                keys.remove((rtype, tagged, '*', otype))
            if otype == '*':
                keys.remove((rtype, tagged, stype, '*'))
        return keys

    def tag_attribute(self, tag, stype, attr):
        self._tagdefs[(str(attr), 'subject', str(stype), '*')] = tag

    def tag_relation(self, tag, relation, tagged):
        assert tagged in ('subject', 'object'), tagged
        stype, rtype, otype = relation
        self._tagdefs[(str(rtype), tagged, str(stype), str(otype))] = tag

    def del_rtag(self, relation, tagged):
        assert tagged in ('subject', 'object'), tagged
        stype, rtype, otype = relation
        del self._tagdefs[(str(rtype), tagged, str(stype), str(otype))]

    def get(self, rtype, tagged, stype='*', otype='*'):
        for key in reversed(self._get_keys(rtype, tagged, stype, otype)):
            try:
                return self._tagdefs[key]
            except KeyError:
                continue
        return None

    def etype_get(self, etype, rtype, tagged, ttype='*'):
        if tagged == 'subject':
            return self.get(rtype, tagged, etype, ttype)
        return self.get(rtype, tagged, ttype, etype)



class RelationTagsSet(RelationTags):
    """This class associates a set of tags to each key."""

    def tag_relation(self, tag, relation, tagged):
        assert tagged in ('subject', 'object'), tagged
        stype, rtype, otype = relation
        rtags = self._tagdefs.setdefault((rtype, tagged, stype, otype), set())
        rtags.add(tag)

    def get(self, rtype, tagged, stype='*', otype='*'):
        rtags = set()
        for key in self._get_keys(rtype, tagged, stype, otype):
            try:
                rtags.update(self._tagdefs[key])
            except KeyError:
                continue
        return rtags
