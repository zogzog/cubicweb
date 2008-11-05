"""contains utility functions and some visual component to restrict results of
a search

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from logilab.common.graph import has_path
from logilab.common.decorators import cached
from logilab.common.compat import all

from logilab.mtconverter import html_escape

from rql import nodes



from cubicweb.web.facet import (VocabularyFacet, prepare_facets_rqlst)


"""Set of base controllers, which are directly plugged into the application
object to handle publication.


:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.deprecation import moved

insert_attr_select_relation = moved('cubicweb.web.facet',
                                    'insert_attr_select_relation')
