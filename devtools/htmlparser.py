"""defines a validating HTML parser used in web application tests"""

import re

from lxml import etree

from cubicweb.view import STRICT_DOCTYPE, TRANSITIONAL_DOCTYPE

ERR_COUNT = 0

class Validator(object):
    
    def parse_string(self, data, sysid=None):
        try:
            data = self.preprocess_data(data)
            return PageInfo(data, etree.fromstring(data, self.parser))
        except etree.XMLSyntaxError, exc:
            def save_in(fname=''):
                file(fname, 'w').write(data)
            new_exc = AssertionError(u'invalid xml %s' % exc)
            new_exc.position = exc.position
            raise new_exc

    def preprocess_data(self, data):
        return data


class DTDValidator(Validator):
    def __init__(self):
        Validator.__init__(self)
        self.parser = etree.XMLParser(dtd_validation=True)

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
        return '<?xml version="1.0" encoding="UTF-8"?>%s\n%s' % (STRICT_DOCTYPE, data)

   
class SaxOnlyValidator(Validator):

    def __init__(self):
        Validator.__init__(self)
        self.parser = etree.XMLParser()

class HTMLValidator(Validator):

    def __init__(self):
        Validator.__init__(self)
        self.parser = etree.HTMLParser()

    

class PageInfo(object):
    """holds various informations on the view's output"""
    def __init__(self, source, root):
        self.source = source
        self.etree = root
        self.source = source
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
        
    def find_tag(self, tag):
        """return a list which contains text of all "tag" elements """
        if self.default_ns is None:
            iterstr = ".//%s" % tag
        else:
            iterstr = ".//{%s}%s" % (self.default_ns, tag)
        if tag in ('a', 'input'):
            return [(elt.text, elt.attrib) for elt in self.etree.iterfind(iterstr)]
        return [u''.join(elt.xpath('.//text()')) for elt in self.etree.iterfind(iterstr)]
         
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
