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
    _allowed_values = None
    def __init__(self, initfunc=None, allowed_values=None):
        self._tagdefs = {}
        if allowed_values is not None:
            self._allowed_values = allowed_values
        self._initfunc = initfunc

    def __repr__(self):
        return repr(self._tagdefs)

    # dict compat
    def __getitem__(self, key):
        return self.get(*key)
    __contains__ = __getitem__

    def _get_keys(self, stype, rtype, otype, tagged):
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

    def init(self, schema):
        # XXX check existing keys against schema
        for rtype, tagged, stype, otype in self._tagdefs:
            assert rtype in schema
            if stype != '*':
                assert stype in schema
            if otype != '*':
                assert otype in schema
        if self._initfunc is not None:
            for eschema in schema.entities():
                for rschema, tschemas, role in eschema.relation_definitions(True):
                    for tschema in tschemas:
                        if role == 'subject':
                            stype, otype = eschema, tschema
                        else:
                            stype, otype = tschema, eschema
                        self._initfunc(stype, rtype, otype, role)

    # rtag declaration api ####################################################

    def tag_attribute(self, key, tag):
        key = list(key)
        key.append('*')
        self.tag_subject_of(key, tag)

    def tag_subject_of(self, key, tag):
        key = list(key)
        key.append('subject')
        self.tag_relation(key, tag)

    def tag_object_of(self, key, tag):
        key = list(key)
        key.append('object')
        self.tag_relation(key, tag)

    def tag_relation(self, key, tag):
        #if isinstance(key, basestring):
        #    stype, rtype, otype = key.split()
        #else:
        stype, rtype, otype, tagged = [str(k) for k in key]
        if self._allowed_values is not None:
            assert tag in self._allowed_values
        self._tagdefs[(rtype, tagged, stype, otype)] = tag

    # rtag runtime api ########################################################

    def del_rtag(self, stype, rtype, otype, tagged):
        del self._tagdefs[(rtype, tagged, stype, otype)]

    def get(self, stype, rtype, otype, tagged):
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

    def tag_relation(self, key, tag):
        stype, rtype, otype, tagged = [str(k) for k in key]
        rtags = self._tagdefs.setdefault((rtype, tagged, stype, otype), set())
        rtags.add(tag)

    def get(self, stype, rtype, otype, tagged):
        rtags = set()
        for key in self._get_keys(stype, rtype, otype, tagged):
            try:
                rtags.update(self._tagdefs[key])
            except KeyError:
                continue
        return rtags


class RelationTagsBool(RelationTags):
    _allowed_values = frozenset((True, False))

    def tag_subject_of(self, key, tag=True):
        super(RelationTagsBool, self).tag_subject_of(key, tag)

    def tag_object_of(self, key, tag=True):
        super(RelationTagsBool, self).tag_object_of(key, tag)

    def tag_attribute(self, key, tag=True):
        super(RelationTagsBool, self).tag_attribute(key, tag)
