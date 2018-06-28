# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""inline help system, rendering ReST files in the `wdoc` subdirectory of
CubicWeb and cubes

"""


import io
from itertools import chain
from os.path import join
from xml.etree.ElementTree import parse

from six import text_type

from logilab.common.registry import yes

from cubicweb.predicates import match_form_params
from cubicweb.view import StartupView
from cubicweb.uilib import rest_publish
from cubicweb.web import NotFound, action
from cubicweb import _

# table of content management #################################################


def build_toc_index(node, parent, index):
    try:
        nodeidx = node.attrib['resource']
        assert nodeidx not in index, nodeidx
        index[nodeidx] = node, parent
    except KeyError:
        pass
    for child in node:
        build_toc_index(child, node, index)


def get_insertion_point(section, index):
    if section.attrib.get('insertafter'):
        snode, node = index[section.attrib['insertafter']]
        idx = list(node).index(snode) + 1
    elif section.attrib.get('insertbefore'):
        snode, node = index[section.attrib['insertbefore']]
        idx = node.getchildren().index(snode)
    elif 'appendto' in section.attrib:
        node, _ = index[section.attrib['appendto']]
        idx = None
    else:
        node, idx = None, None
    return node, idx


def build_toc(config):
    alltocfiles = reversed(tuple(config.locate_all_files('toc.xml')))
    maintoc = parse(next(alltocfiles)).getroot()
    index = {}
    build_toc_index(maintoc, None, index)
    # insert component documentation into the tree according to their toc.xml
    # file
    for fpath in alltocfiles:
        toc = parse(fpath).getroot()
        for section in toc:
            node, idx = get_insertion_point(section, index)
            if node is None:
                continue
            if idx is None:
                node.append(section)
            else:
                node.insert(idx, section)
            build_toc_index(section, node, index)
    return index


def title_for_lang(node, lang):
    fallback_title = None
    for title in node.findall('title'):
        title_lang = title.attrib['{http://www.w3.org/XML/1998/namespace}lang']
        if title_lang == lang:
            return text_type(title.text)
        if title_lang == 'en':
            fallback_title = text_type(title.text)
    return fallback_title


def subsections(node):
    return [child for child in node if child.tag == 'section']

# help views ##################################################################


class InlineHelpView(StartupView):
    __select__ = match_form_params('fid')
    __regid__ = 'wdoc'
    title = _('site documentation')

    def call(self):
        fid = self._cw.form['fid']
        vreg = self._cw.vreg
        for lang in chain((self._cw.lang, vreg.property_value('ui.language')),
                          vreg.config.available_languages()):
            rid = '%s_%s.rst' % (fid, lang)
            resourcedir = vreg.config.locate_doc_file(rid)
            if resourcedir:
                break
        else:
            raise NotFound
        self.tocindex = build_toc(vreg.config)
        try:
            node, parent = self.tocindex[fid]
        except KeyError:
            node, parent = None, None
        else:
            self.navigation_links(node, parent)
            self.w(u'<div class="hr"></div>')
            self.w(u'<h1>%s</h1>' % (title_for_lang(node, self._cw.lang)))
        with io.open(join(resourcedir, rid)) as f:
            self.w(rest_publish(self, f.read()))
        if node is not None:
            self.subsections_links(node)
            self.w(u'<div class="hr"></div>')
            self.navigation_links(node, parent)

    def navigation_links(self, node, parent):
        if parent is None:
            return
        brothers = subsections(parent)
        self.w(u'<div class="docnav">\n')
        previousidx = brothers.index(node) - 1
        if previousidx >= 0:
            self.navsection(brothers[previousidx], 'prev')
        self.navsection(parent, 'up')
        nextidx = brothers.index(node) + 1
        if nextidx < len(brothers):
            self.navsection(brothers[nextidx], 'next')
        self.w(u'</div>\n')

    navinfo = {'prev': ('', 'data/previous.png', _('i18nprevnext_previous')),
               'next': ('', 'data/next.png', _('i18nprevnext_next')),
               'up': ('', 'data/up.png', _('i18nprevnext_up'))}

    def navsection(self, node, navtype):
        htmlclass, imgpath, msgid = self.navinfo[navtype]
        self.w(u'<span class="%s">' % htmlclass)
        self.w(u'%s : ' % self._cw._(msgid))
        self.w(u'<a href="%s">%s</a>' % (
            self._cw.build_url('doc/' + node.attrib['resource']),
            title_for_lang(node, self._cw.lang)))
        self.w(u'</span>\n')

    def subsections_links(self, node, first=True):
        sub = subsections(node)
        if not sub:
            return
        if first:
            self.w(u'<div class="hr"></div>')
        self.w(u'<ul class="docsum">')
        for child in sub:
            self.w(u'<li><a href="%s">%s</a>' % (
                self._cw.build_url('doc/' + child.attrib['resource']),
                title_for_lang(child, self._cw.lang)))
            self.subsections_links(child, False)
            self.w(u'</li>')
        self.w(u'</ul>\n')


class InlineHelpImageView(StartupView):
    __regid__ = 'wdocimages'
    __select__ = match_form_params('fid')
    binary = True
    templatable = False
    content_type = 'image/png'

    def call(self):
        fid = self._cw.form['fid']
        for lang in chain((self._cw.lang, self._cw.vreg.property_value('ui.language')),
                          self._cw.vreg.config.available_languages()):
            rid = join('images', '%s_%s.png' % (fid, lang))
            resourcedir = self._cw.vreg.config.locate_doc_file(rid)
            if resourcedir:
                break
        else:
            raise NotFound
        with io.open(join(resourcedir, rid)) as f:
            self.w(f.read())


class HelpAction(action.Action):
    __regid__ = 'help'
    __select__ = yes()

    category = 'footer'
    order = 0
    title = _('Help')

    def url(self):
        return self._cw.build_url('doc/main')


class AboutAction(action.Action):
    __regid__ = 'about'
    __select__ = yes()

    category = 'footer'
    order = 2
    title = _('About this site')

    def url(self):
        return self._cw.build_url('doc/about')
