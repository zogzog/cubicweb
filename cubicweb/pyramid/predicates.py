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
