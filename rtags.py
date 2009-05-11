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

    def _get_tagged(self, stype, otype, tagged=None):
        stype, otype = str(stype), str(otype)
        if tagged is None:
            if stype[0] == '!':
                tagged = 'subject'
                stype = stype[1:]
            elif otype[0] == '!':
                tagged = 'object'
                otype = otype[1:]
            else:
                raise AssertionError('either stype or rtype should have the '
                                     'role mark ("!")')
        else:
            assert tagged in ('subject', 'object'), tagged
        return stype, otype, tagged

    def _get_keys(self, stype, rtype, otype, tagged=None):
        stype, otype, tagged = self._get_tagged(stype, otype, tagged)
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

    def tag_relation(self, stype, rtype, otype, tag, tagged=None):
        stype, otype, tagged = self._get_tagged(stype, otype, tagged)
        self._tagdefs[(str(rtype), tagged, stype, otype)] = tag

    def tag_attribute(self, stype, attr, tag):
        self.tag_relation(stype, attr, '*', tag, tagged)

    def del_rtag(self, stype, rtype, otype):
        stype, otype, tagged = self._get_tagged(stype, otype)
        del self._tagdefs[(str(rtype), tagged, stype, otype)]

    def get(self, stype, rtype, otype, tagged=None):
        for key in reversed(self._get_keys(stype, rtype, otype, tagged)):
            try:
                return self._tagdefs[key]
            except KeyError:
                continue
        return None

    def etype_get(self, etype, rtype, role, ttype='*'):
        if role == 'subject':
            return self.get(etype, rtype, ttype, role)
        return self.get(ttype, rtype, etype, role)



class RelationTagsSet(RelationTags):
    """This class associates a set of tags to each key."""

    def tag_relation(self, stype, rtype, otype, tag, tagged=None):
        stype, otype, tagged = self._get_tagged(stype, otype, tagged)
        rtags = self._tagdefs.setdefault((rtype, tagged, stype, otype), set())
        rtags.add(tag)

    def get(self, stype, rtype, otype, tagged=None):
        rtags = set()
        for key in self._get_keys(stype, rtype, otype, tagged):
            try:
                rtags.update(self._tagdefs[key])
            except KeyError:
                continue
        return rtags
