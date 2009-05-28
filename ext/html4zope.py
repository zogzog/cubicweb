# Author: David Goodger
"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
# Contact: goodger@users.sourceforge.net
# Revision: $Revision: 1.2 $
# Date: $Date: 2005-07-04 16:36:50 $
# Copyright: This module has been placed in the public domain.

"""
Simple HyperText Markup Language document tree Writer.

The output conforms to the HTML 4.01 Transitional DTD and to the Extensible
HTML version 1.0 Transitional DTD (*almost* strict).  The output contains a
minimum of formatting information.  A cascading style sheet ("default.css" by
default) is required for proper viewing with a modern graphical browser.

http://cvs.zope.org/Zope/lib/python/docutils/writers/Attic/html4zope.py?rev=1.1.2.2&only_with_tag=ajung-restructuredtext-integration-branch&content-type=text/vnd.viewcvs-markup
"""

__docformat__ = 'reStructuredText'

from logilab.mtconverter import html_escape

from docutils import nodes
from docutils.writers.html4css1 import Writer as CSS1Writer
from docutils.writers.html4css1 import HTMLTranslator as CSS1HTMLTranslator
import os

default_level = int(os.environ.get('STX_DEFAULT_LEVEL', 3))

class Writer(CSS1Writer):
    """css writer using our html translator"""
    def __init__(self, base_url):
        CSS1Writer.__init__(self)
        self.translator_class = URLBinder(base_url, HTMLTranslator)

    def apply_template(self):
        """overriding this is necessary with docutils >= 0.5"""
        return self.visitor.astext()

class URLBinder:
    def __init__(self, url, klass):
        self.base_url = url
        self.translator_class = HTMLTranslator

    def __call__(self, document):
        translator = self.translator_class(document)
        translator.base_url = self.base_url
        return translator

class HTMLTranslator(CSS1HTMLTranslator):
    """ReST tree to html translator"""

    def astext(self):
        """return the extracted html"""
        return ''.join(self.body)

    def visit_title(self, node):
        """Only 6 section levels are supported by HTML."""
        if isinstance(node.parent, nodes.topic):
            self.body.append(
                  self.starttag(node, 'p', '', CLASS='topic-title'))
            if node.parent.hasattr('id'):
                self.body.append(
                    self.starttag({}, 'a', '', name=node.parent['id']))
                self.context.append('</a></p>\n')
            else:
                self.context.append('</p>\n')
        elif self.section_level == 0:
            # document title
            self.head.append('<title>%s</title>\n'
                             % self.encode(node.astext()))
            self.body.append(self.starttag(node, 'h%d' % default_level, '',
                                           CLASS='title'))
            self.context.append('</h%d>\n' % default_level)
        else:
            self.body.append(
                  self.starttag(node, 'h%s' % (
                default_level+self.section_level-1), ''))
            atts = {}
            if node.hasattr('refid'):
                atts['class'] = 'toc-backref'
                atts['href'] = '%s#%s' % (self.base_url, node['refid'])
            self.body.append(self.starttag({}, 'a', '', **atts))
            self.context.append('</a></h%s>\n' % (
                default_level+self.section_level-1))

    def visit_subtitle(self, node):
        """format a subtitle"""
        if isinstance(node.parent, nodes.sidebar):
            self.body.append(self.starttag(node, 'p', '',
                                           CLASS='sidebar-subtitle'))
            self.context.append('</p>\n')
        else:
            self.body.append(
                  self.starttag(node, 'h%s' % (default_level+1), '',
                                CLASS='subtitle'))
            self.context.append('</h%s>\n' % (default_level+1))

    def visit_document(self, node):
        """syt: i don't want the enclosing <div class="document">"""
    def depart_document(self, node):
        """syt: i don't want the enclosing <div class="document">"""

    def visit_reference(self, node):
        """syt: i want absolute urls"""
        if node.has_key('refuri'):
            href = node['refuri']
            if ( self.settings.cloak_email_addresses
                 and href.startswith('mailto:')):
                href = self.cloak_mailto(href)
                self.in_mailto = 1
        else:
            assert node.has_key('refid'), \
                   'References must have "refuri" or "refid" attribute.'
            href = '%s#%s' % (self.base_url, node['refid'])
        atts = {'href': href, 'class': 'reference'}
        if not isinstance(node.parent, nodes.TextElement):
            assert len(node) == 1 and isinstance(node[0], nodes.image)
            atts['class'] += ' image-reference'
        self.body.append(self.starttag(node, 'a', '', **atts))

    ## override error messages to avoid XHTML problems ########################
    def visit_problematic(self, node):
        pass

    def depart_problematic(self, node):
        pass

    def visit_system_message(self, node):
        backref_text = ''
        if len(node['backrefs']):
            backrefs = node['backrefs']
            if len(backrefs) == 1:
                backref_text = '; <em>backlink</em>'
            else:
                i = 1
                backlinks = []
                for backref in backrefs:
                    backlinks.append(str(i))
                    i += 1
                backref_text = ('; <em>backlinks: %s</em>'
                                % ', '.join(backlinks))
        if node.hasattr('line'):
            line = ', line %s' % node['line']
        else:
            line = ''
        a_start = a_end = ''
        error = u'System Message: %s%s/%s%s (%s %s)%s</p>\n' % (
            a_start, node['type'], node['level'], a_end,
            self.encode(node['source']), line, backref_text)
        self.body.append(u'<div class="system-message"><b>ReST / HTML errors:</b>%s</div>' % html_escape(error))

    def depart_system_message(self, node):
        pass
