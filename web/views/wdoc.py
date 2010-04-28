# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""inline help system, using ReST file in products `wdoc` directory

"""
__docformat__ = "restructuredtext en"

from itertools import chain
from os.path import join
from bisect import bisect_right
from datetime import date

from logilab.common.changelog import ChangeLog
from logilab.common.date import strptime, todate
from logilab.mtconverter import CHARSET_DECL_RGX

from cubicweb.selectors import match_form_params, yes
from cubicweb.view import StartupView
from cubicweb.uilib import rest_publish
from cubicweb.web import NotFound, action
_ = unicode

# table of content management #################################################

try:
    from xml.etree.ElementTree import parse
except ImportError:
    from elementtree.ElementTree import parse

def build_toc_index(node, index):
    try:
        nodeidx = node.attrib['resource']
        assert not nodeidx in index, nodeidx
        index[nodeidx] = node
    except KeyError:
        pass
    for child in node:
        build_toc_index(child, index)
        child.parent = node

def get_insertion_point(section, index):
    if section.attrib.get('insertafter'):
        snode = index[section.attrib['insertafter']]
        node = snode.parent
        idx = node.getchildren().index(snode) + 1
    elif section.attrib.get('insertbefore'):
        snode = index[section.attrib['insertbefore']]
        node = snode.parent
        idx = node.getchildren().index(snode)
    else:
        node = index[section.attrib['appendto']]
        idx = None
    return node, idx

def build_toc(config):
    alltocfiles = reversed(tuple(config.locate_all_files('toc.xml')))
    maintoc = parse(alltocfiles.next()).getroot()
    maintoc.parent = None
    index = {}
    build_toc_index(maintoc, index)
    # insert component documentation into the tree according to their toc.xml
    # file
    for fpath in alltocfiles:
        toc = parse(fpath).getroot()
        for section in toc:
            node, idx = get_insertion_point(section, index)
            if idx is None:
                node.append(section)
            else:
                node.insert(idx, section)
            section.parent = node
            build_toc_index(section, index)
    return index

def title_for_lang(node, lang):
    for title in node.findall('title'):
        if title.attrib['{http://www.w3.org/XML/1998/namespace}lang'] == lang:
            return unicode(title.text)

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
            node = self.tocindex[fid]
        except KeyError:
            node = None
        else:
            self.navigation_links(node)
            self.w(u'<div class="hr"></div>')
            self.w(u'<h1>%s</h1>' % (title_for_lang(node, self._cw.lang)))
        data = open(join(resourcedir, rid)).read()
        self.w(rest_publish(self, data))
        if node is not None:
            self.subsections_links(node)
            self.w(u'<div class="hr"></div>')
            self.navigation_links(node)

    def navigation_links(self, node):
        req = self._cw
        parent = node.parent
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
            self._cw.build_url('doc/'+node.attrib['resource']),
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
                self._cw.build_url('doc/'+child.attrib['resource']),
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
        self.w(open(join(resourcedir, rid)).read())


class ChangeLogView(StartupView):
    __regid__ = 'changelog'
    title = _('What\'s new?')
    maxentries = 25

    def call(self):
        rid = 'ChangeLog_%s' % (self._cw.lang)
        allentries = []
        title = self._cw._(self.title)
        restdata = ['.. -*- coding: utf-8 -*-', '', title, '='*len(title), '']
        w = restdata.append
        today = date.today()
        for fpath in self._cw.vreg.config.locate_all_files(rid):
            cl = ChangeLog(fpath)
            encoding = 'utf-8'
            # additional content may be found in title
            for line in (cl.title + cl.additional_content).splitlines():
                m = CHARSET_DECL_RGX.search(line)
                if m is not None:
                    encoding = m.group(1)
                    continue
                elif line.startswith('.. '):
                    w(unicode(line, encoding))
            for entry in cl.entries:
                if entry.date:
                    edate = todate(strptime(entry.date, '%Y-%m-%d'))
                else:
                    edate = today
                messages = []
                for msglines, submsgs in entry.messages:
                    msgstr = unicode(' '.join(l.strip() for l in msglines), encoding)
                    msgstr += u'\n\n'
                    for submsglines in submsgs:
                        msgstr += '     - ' + unicode(' '.join(l.strip() for l in submsglines), encoding)
                        msgstr += u'\n'
                    messages.append(msgstr)
                entry = (edate, messages)
                allentries.insert(bisect_right(allentries, entry), entry)
        latestdate = None
        i = 0
        for edate, messages in reversed(allentries):
            if latestdate != edate:
                fdate = self._cw.format_date(edate)
                w(u'\n%s' % fdate)
                w('~' * len(fdate))
                latestdate = edate
            for msg in messages:
                w(u'* %s' % msg)
                i += 1
                if i > self.maxentries:
                    break
        w('') # blank line
        self.w(rest_publish(self, '\n'.join(restdata)))


class HelpAction(action.Action):
    __regid__ = 'help'
    __select__ = yes()

    category = 'footer'
    order = 0
    title = _('Help')

    def url(self):
        return self._cw.build_url('doc/main')

class ChangeLogAction(action.Action):
    __regid__ = 'changelog'
    __select__ = yes()

    category = 'footer'
    order = 1
    title = ChangeLogView.title

    def url(self):
        return self._cw.build_url('changelog')


class AboutAction(action.Action):
    __regid__ = 'about'
    __select__ = yes()

    category = 'footer'
    order = 2
    title = _('about this site')

    def url(self):
        return self._cw.build_url('doc/about')

