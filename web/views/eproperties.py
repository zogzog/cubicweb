"""Specific views for EProperty


:organization: Logilab
:copyright: 2007-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.selectors import implements
from cubicweb.web.views import baseviews

class EPropertyPrimaryView(baseviews.PrimaryView):
    __selectors__ = implements('EProperty')
    skip_none = False
