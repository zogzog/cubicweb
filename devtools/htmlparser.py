# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""defines a validating HTML parser used in web application tests"""

import re
import sys
from xml import sax
from cStringIO import StringIO

from lxml import etree

from logilab.common.deprecation import class_deprecated, class_renamed

from cubicweb.view import STRICT_DOCTYPE, TRANSITIONAL_DOCTYPE

STRICT_DOCTYPE = str(STRICT_DOCTYPE)
TRANSITIONAL_DOCTYPE = str(TRANSITIONAL_DOCTYPE)

ERR_COUNT = 0

_REM_SCRIPT_RGX = re.compile(r"<script[^>]*>.*?</script>", re.U|re.M|re.I|re.S)
def _remove_script_tags(data):
    """Remove the script (usually javascript) tags to help the lxml
    XMLParser / HTMLParser do their job. Without that, they choke on
    tags embedded in JS strings.
    """
    # Notice we may want to use lxml cleaner, but it's far too intrusive:
    #
    # cleaner = Cleaner(scripts=True,
    #                   javascript=False,
    #                   comments=False,
    #                   style=False,
    #                   links=False,
    #                   meta=False,
    #                   page_structure=False,
    #                   processing_instructions=False,
    #                   embedded=False,
    #                   frames=False,
    #                   forms=False,
    #                   annoying_tags=False,
    #                   remove_tags=(),
    #                   remove_unknown_tags=False,
    #                   safe_attrs_only=False,
    #                   add_nofollow=False)
    # >>> cleaner.clean_html('<body></body>')
    # '<span></span>'
    # >>> cleaner.clean_html('<!DOCTYPE html><body></body>')
    # '<html><body></body></html>'
    # >>> cleaner.clean_html('<body><div/></body>')
    # '<div></div>'
    # >>> cleaner.clean_html('<html><body><div/><br></body><html>')
    # '<html><body><div></div><br></body></html>'
    # >>> cleaner.clean_html('<html><body><div/><br><span></body><html>')
    # '<html><body><div></div><br><span></span></body></html>'
    #
    # using that, we'll miss most actual validation error we want to
    # catch. For now, use dumb regexp
    return _REM_SCRIPT_RGX.sub('', data)


class Validator(object):
    """ base validator API """
    parser = None

    def parse_string(self, source):
        etree = self._parse(self.preprocess_data(source))
        return PageInfo(source, etree)

    def preprocess_data(self, data):
        return data

    def _parse(self, pdata):
        try:
            return etree.fromstring(pdata, self.parser)
        except etree.XMLSyntaxError as exc:
            def save_in(fname=''):
                file(fname, 'w').write(data)
            new_exc = AssertionError(u'invalid document: %s' % exc)
            new_exc.position = exc.position
            raise new_exc


class DTDValidator(Validator):
    def __init__(self):
        Validator.__init__(self)
        # XXX understand what's happening under windows
        self.parser = etree.XMLParser(dtd_validation=sys.platform != 'win32')

    def preprocess_data(self, data):
        """used to fix potential blockquote mess generated by docutils"""
        if STRICT_DOCTYPE not in data:
            return data
        # parse using transitional DTD
        data = data.replace(STRICT_DOCTYPE, TRANSITIONAL_DOCTYPE)
        tree = etree.fromstring(data, self.parser)
        namespace = tree.nsmap.get(None)
        # this is the list of authorized child tags for <blockquote> nodes
        expected = 'p h1 h2 h3 h4 h5 h6 div ul ol dl pre hr blockquote address ' \
                   'fieldset table form noscript ins del script'.split()
        if namespace:
            blockquotes = tree.findall('.//{%s}blockquote' % namespace)
            expected = ['{%s}%s' % (namespace, tag) for tag in expected]
        else:
            blockquotes = tree.findall('.//blockquote')
        # quick and dirty approach: remove all blockquotes
        for blockquote in blockquotes:
            parent = blockquote.getparent()
            parent.remove(blockquote)
        data = etree.tostring(tree)
        return '<?xml version="1.0" encoding="UTF-8"?>%s\n%s' % (
            STRICT_DOCTYPE, data)


class XMLValidator(Validator):
    """XML validator, checks that XML is well-formed and used XMLNS are defined"""

    def __init__(self):
        Validator.__init__(self)
        self.parser = etree.XMLParser()

SaxOnlyValidator = class_renamed('SaxOnlyValidator',
                                 XMLValidator,
                                 '[3.17] you should use the '
                                 'XMLValidator class instead')


class XMLSyntaxValidator(Validator):
    """XML syntax validator, check XML is well-formed"""

    class MySaxErrorHandler(sax.ErrorHandler):
        """override default handler to avoid choking because of unknown entity"""
        def fatalError(self, exception):
            # XXX check entity in htmlentitydefs
            if not str(exception).endswith('undefined entity'):
                raise exception
    _parser = sax.make_parser()
    _parser.setContentHandler(sax.handler.ContentHandler())
    _parser.setErrorHandler(MySaxErrorHandler())

    def __init__(self):
        super(XMLSyntaxValidator, self).__init__()
        # XMLParser() wants xml namespaces defined
        # XMLParser(recover=True) will accept almost anything
        #
        # -> use the later but preprocess will check xml well-formness using a
        #    dumb SAX parser
        self.parser = etree.XMLParser(recover=True)

    def preprocess_data(self, data):
        return _remove_script_tags(data)

    def _parse(self, data):
        inpsrc = sax.InputSource()
        inpsrc.setByteStream(StringIO(data))
        try:
            self._parser.parse(inpsrc)
        except sax.SAXParseException, exc:
            new_exc = AssertionError(u'invalid document: %s' % exc)
            new_exc.position = (exc._linenum, exc._colnum)
            raise new_exc
        return super(XMLSyntaxValidator, self)._parse(data)


class XMLDemotingValidator(XMLValidator):
    """ some views produce html instead of xhtml, using demote_to_html

    this is typically related to the use of external dependencies
    which do not produce valid xhtml (google maps, ...)
    """
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.10] this is now handled in testlib.py'

    def preprocess_data(self, data):
        if data.startswith('<?xml'):
            self.parser = etree.XMLParser()
        else:
            self.parser = etree.HTMLParser()
        return data


class HTMLValidator(Validator):

    def __init__(self):
        Validator.__init__(self)
        self.parser = etree.HTMLParser(recover=False)

    def preprocess_data(self, data):
        return _remove_script_tags(data)


class PageInfo(object):
    """holds various informations on the view's output"""
    def __init__(self, source, root):
        self.source = source
        self.etree = root
        self.raw_text = u''.join(root.xpath('//text()'))
        self.namespace = self.etree.nsmap
        self.default_ns = self.namespace.get(None)
        self.a_tags = self.find_tag('a')
        self.h1_tags = self.find_tag('h1')
        self.h2_tags = self.find_tag('h2')
        self.h3_tags = self.find_tag('h3')
        self.h4_tags = self.find_tag('h4')
        self.input_tags = self.find_tag('input')
        self.title_tags = [self.h1_tags, self.h2_tags, self.h3_tags, self.h4_tags]

    def _iterstr(self, tag):
        if self.default_ns is None:
            return ".//%s" % tag
        else:
            return ".//{%s}%s" % (self.default_ns, tag)

    def matching_nodes(self, tag, **attrs):
        for elt in self.etree.iterfind(self._iterstr(tag)):
            eltattrs  = elt.attrib
            for attr, value in attrs.iteritems():
                try:
                    if eltattrs[attr] != value:
                        break
                except KeyError:
                    break
            else: # all attributes match
                yield elt

    def has_tag(self, tag, nboccurs=1, **attrs):
        """returns True if tag with given attributes appears in the page
        `nbtimes` (any if None)
        """
        for elt in self.matching_nodes(tag, **attrs):
            if nboccurs is None: # no need to check number of occurences
                return True
            if not nboccurs: # too much occurences
                return False
            nboccurs -= 1
        if nboccurs == 0: # correct number of occurences
            return True
        return False # no matching tag/attrs

    def find_tag(self, tag, gettext=True):
        """return a list which contains text of all "tag" elements """
        iterstr = self._iterstr(tag)
        if not gettext or tag in ('a', 'input'):
            return [(elt.text, elt.attrib)
                    for elt in self.etree.iterfind(iterstr)]
        return [u''.join(elt.xpath('.//text()'))
                for elt in self.etree.iterfind(iterstr)]

    def appears(self, text):
        """returns True if <text> appears in the page"""
        return text in self.raw_text

    def __contains__(self, text):
        return text in self.source

    def has_title(self, text, level=None):
        """returns True if <h?>text</h?>

        :param level: the title's level (1 for h1, 2 for h2, etc.)
        """
        if level is None:
            for hlist in self.title_tags:
                if text in hlist:
                    return True
            return False
        else:
            hlist = self.title_tags[level - 1]
            return text in hlist

    def has_title_regexp(self, pattern, level=None):
        """returns True if <h?>pattern</h?>"""
        sre = re.compile(pattern)
        if level is None:
            for hlist in self.title_tags:
                for title in hlist:
                    if sre.match(title):
                        return True
            return False
        else:
            hlist = self.title_tags[level - 1]
            for title in hlist:
                if sre.match(title):
                    return True
            return False

    def has_link(self, text, url=None):
        """returns True if <a href=url>text</a> was found in the page"""
        for link_text, attrs in self.a_tags:
            if text == link_text:
                if url is None:
                    return True
                try:
                    href = attrs['href']
                    if href == url:
                        return True
                except KeyError:
                    continue
        return False

    def has_link_regexp(self, pattern, url=None):
        """returns True if <a href=url>pattern</a> was found in the page"""
        sre = re.compile(pattern)
        for link_text, attrs in self.a_tags:
            if sre.match(link_text):
                if url is None:
                    return True
                try:
                    href = attrs['href']
                    if href == url:
                        return True
                except KeyError:
                    continue
        return False

VALMAP = {None: None,
          'dtd': DTDValidator,
          'xml': XMLValidator,
          'html': HTMLValidator,
          }
