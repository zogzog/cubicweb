"""Common subpackage of cubicweb : defines library functions used both on the
hg stserver side and on the client side

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.adbh import FunctionDescr

from cubicweb._exceptions import * # bw compat

from rql.utils import register_function, iter_funcnode_variables

class COMMA_JOIN(FunctionDescr):
    supported_backends = ('postgres', 'sqlite',)
    rtype = 'String'

    @classmethod
    def st_description(cls, funcnode, mainindex, tr):
        return ', '.join(sorted(term.get_description(mainindex, tr)
                                for term in iter_funcnode_variables(funcnode)))

register_function(COMMA_JOIN)  # XXX do not expose?


class CONCAT_STRINGS(COMMA_JOIN):
    aggregat = True

register_function(CONCAT_STRINGS) # XXX bw compat

class GROUP_CONCAT(CONCAT_STRINGS):
    supported_backends = ('mysql', 'postgres', 'sqlite',)

register_function(GROUP_CONCAT)


class LIMIT_SIZE(FunctionDescr):
    supported_backends = ('postgres', 'sqlite',)
    rtype = 'String'

    @classmethod
    def st_description(cls, funcnode, mainindex, tr):
        return funcnode.children[0].get_description(mainindex, tr)

register_function(LIMIT_SIZE)


class TEXT_LIMIT_SIZE(LIMIT_SIZE):
    supported_backends = ('mysql', 'postgres', 'sqlite',)

register_function(TEXT_LIMIT_SIZE)
