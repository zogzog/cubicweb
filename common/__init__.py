"""Common subpackage of cubicweb : defines library functions used both on the
hg stserver side and on the client side

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

from logilab.common.adbh import FunctionDescr

from cubicweb._exceptions import * # bw compat

from rql.utils import register_function, iter_funcnode_variables

class COMMA_JOIN(FunctionDescr):
    supported_backends = ('postgres', 'sqlite',)
    rtype = 'String'
    
    @classmethod
    def st_description(cls, funcnode):
        return ', '.join(term.get_description()
                         for term in iter_funcnode_variables(funcnode))
    
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
    def st_description(cls, funcnode):
        return funcnode.children[0].get_description()
    
register_function(LIMIT_SIZE)


class TEXT_LIMIT_SIZE(LIMIT_SIZE):
    supported_backends = ('mysql', 'postgres', 'sqlite',)
    
register_function(TEXT_LIMIT_SIZE)
