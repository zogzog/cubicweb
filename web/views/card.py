"""Specific views for cards

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.selectors import implements
from cubicweb.web.views import baseviews
from logilab.mtconverter import html_escape

_ = unicode

class CardPrimaryView(baseviews.PrimaryView):
    __selectors__ = implements('Card')
    skip_attrs = baseviews.PrimaryView.skip_attrs + ('title', 'synopsis', 'wikiid')
    show_attr_label = False

    def content_title(self, entity):
        return html_escape(entity.dc_title())
    
    def summary(self, entity):
        return html_escape(entity.dc_description())


class CardInlinedView(CardPrimaryView):
    """hide card title and summary"""
    id = 'inlined'
    title = _('inlined view')
    main_related_section = False
    
    def render_entity_title(self, entity):
        pass
    
    def render_entity_metadata(self, entity):
        pass
