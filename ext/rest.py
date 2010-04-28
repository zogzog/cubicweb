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
"""rest publishing functions

contains some functions and setup of docutils for cubicweb. Provides the
following ReST directives:

* `eid`, create link to entity in the repository by their eid

* `card`, create link to card entity in the repository by their wikiid
  (proposing to create it when the refered card doesn't exist yet)

* `winclude`, reference to a web documentation file (in wdoc/ directories)

* `sourcecode` (if pygments is installed), source code colorization

"""
__docformat__ = "restructuredtext en"

from cStringIO import StringIO
from itertools import chain
from logging import getLogger
from os.path import join

from docutils import statemachine, nodes, utils, io
from docutils.core import Publisher
from docutils.parsers.rst import Parser, states, directives
from docutils.parsers.rst.roles import register_canonical_role, set_classes

from logilab.mtconverter import ESC_UCAR_TABLE, ESC_CAR_TABLE, xml_escape

from cubicweb import UnknownEid
from cubicweb.ext.html4zope import Writer

# We provide our own parser as an attempt to get rid of
# state machine reinstanciation

import re
# compile states.Body patterns
for k, v in states.Body.patterns.items():
    if isinstance(v, str):
        states.Body.patterns[k] = re.compile(v)

# register ReStructured Text mimetype / extensions
import mimetypes
mimetypes.add_type('text/rest', '.rest')
mimetypes.add_type('text/rest', '.rst')


LOGGER = getLogger('cubicweb.rest')

def eid_reference_role(role, rawtext, text, lineno, inliner,
                       options={}, content=[]):
    try:
        try:
            eid_num, rest = text.split(u':', 1)
        except:
            eid_num, rest = text, '#'+text
        eid_num = int(eid_num)
        if eid_num < 0:
            raise ValueError
    except ValueError:
        msg = inliner.reporter.error(
            'EID number must be a positive number; "%s" is invalid.'
            % text, line=lineno)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]
    # Base URL mainly used by inliner.pep_reference; so this is correct:
    context = inliner.document.settings.context
    try:
        refedentity = context._cw.entity_from_eid(eid_num)
    except UnknownEid:
        ref = '#'
        rest += u' ' + context._cw._('(UNEXISTANT EID)')
    else:
        ref = refedentity.absolute_url()
    set_classes(options)
    return [nodes.reference(rawtext, utils.unescape(rest), refuri=ref,
                            **options)], []


def winclude_directive(name, arguments, options, content, lineno,
                       content_offset, block_text, state, state_machine):
    """Include a reST file as part of the content of this reST file.

    same as standard include directive but using config.locate_doc_resource to
    get actual file to include.

    Most part of this implementation is copied from `include` directive defined
    in `docutils.parsers.rst.directives.misc`
    """
    context = state.document.settings.context
    cw = context._cw
    source = state_machine.input_lines.source(
        lineno - state_machine.input_offset - 1)
    #source_dir = os.path.dirname(os.path.abspath(source))
    fid = arguments[0]
    for lang in chain((cw.lang, cw.vreg.property_value('ui.language')),
                      cw.vreg.config.available_languages()):
        rid = '%s_%s.rst' % (fid, lang)
        resourcedir = cw.vreg.config.locate_doc_file(rid)
        if resourcedir:
            break
    else:
        severe = state_machine.reporter.severe(
              'Problems with "%s" directive path:\nno resource matching %s.'
              % (name, fid),
              nodes.literal_block(block_text, block_text), line=lineno)
        return [severe]
    path = join(resourcedir, rid)
    encoding = options.get('encoding', state.document.settings.input_encoding)
    try:
        state.document.settings.record_dependencies.add(path)
        include_file = io.FileInput(
            source_path=path, encoding=encoding,
            error_handler=state.document.settings.input_encoding_error_handler,
            handle_io_errors=None)
    except IOError, error:
        severe = state_machine.reporter.severe(
              'Problems with "%s" directive path:\n%s: %s.'
              % (name, error.__class__.__name__, error),
              nodes.literal_block(block_text, block_text), line=lineno)
        return [severe]
    try:
        include_text = include_file.read()
    except UnicodeError, error:
        severe = state_machine.reporter.severe(
              'Problem with "%s" directive:\n%s: %s'
              % (name, error.__class__.__name__, error),
              nodes.literal_block(block_text, block_text), line=lineno)
        return [severe]
    if options.has_key('literal'):
        literal_block = nodes.literal_block(include_text, include_text,
                                            source=path)
        literal_block.line = 1
        return literal_block
    else:
        include_lines = statemachine.string2lines(include_text,
                                                  convert_whitespace=1)
        state_machine.insert_input(include_lines, path)
        return []

winclude_directive.arguments = (1, 0, 1)
winclude_directive.options = {'literal': directives.flag,
                              'encoding': directives.encoding}

try:
    from pygments import highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters import HtmlFormatter
except ImportError:
    pygments_directive = None
else:
    _PYGMENTS_FORMATTER = HtmlFormatter()

    def pygments_directive(name, arguments, options, content, lineno,
                           content_offset, block_text, state, state_machine):
        try:
            lexer = get_lexer_by_name(arguments[0])
        except ValueError:
            # no lexer found
            lexer = get_lexer_by_name('text')
        parsed = highlight(u'\n'.join(content), lexer, _PYGMENTS_FORMATTER)
        # don't fail if no context set on the sourcecode directive
        try:
            context = state.document.settings.context
            context._cw.add_css('pygments.css')
        except AttributeError:
            # used outside cubicweb
            pass
        return [nodes.raw('', parsed, format='html')]

    pygments_directive.arguments = (1, 0, 1)
    pygments_directive.content = 1


class CubicWebReSTParser(Parser):
    """The (customized) reStructuredText parser."""

    def __init__(self):
        self.initial_state = 'Body'
        self.state_classes = states.state_classes
        self.inliner = states.Inliner()
        self.statemachine = states.RSTStateMachine(
              state_classes=self.state_classes,
              initial_state=self.initial_state,
              debug=0)

    def parse(self, inputstring, document):
        """Parse `inputstring` and populate `document`, a document tree."""
        self.setup_parse(inputstring, document)
        inputlines = statemachine.string2lines(inputstring,
                                               convert_whitespace=1)
        self.statemachine.run(inputlines, document, inliner=self.inliner)
        self.finish_parse()


# XXX docutils keep a ref on context, can't find a correct way to remove it
class CWReSTPublisher(Publisher):
    def __init__(self, context, settings, **kwargs):
        Publisher.__init__(self, **kwargs)
        self.set_components('standalone', 'restructuredtext', 'pseudoxml')
        self.process_programmatic_settings(None, settings, None)
        self.settings.context = context


def rest_publish(context, data):
    """publish a string formatted as ReStructured Text to HTML

    :type context: a cubicweb application object

    :type data: str
    :param data: some ReST text

    :rtype: unicode
    :return:
      the data formatted as HTML or the original data if an error occured
    """
    req = context._cw
    if isinstance(data, unicode):
        encoding = 'unicode'
        # remove unprintable characters unauthorized in xml
        data = data.translate(ESC_UCAR_TABLE)
    else:
        encoding = req.encoding
        # remove unprintable characters unauthorized in xml
        data = data.translate(ESC_CAR_TABLE)
    settings = {'input_encoding': encoding, 'output_encoding': 'unicode',
                'warning_stream': StringIO(),
                # dunno what's the max, severe is 4, and we never want a crash
                # (though try/except may be a better option...)
                'halt_level': 10,
                }
    if context:
        if hasattr(req, 'url'):
            base_url = req.url()
        elif hasattr(context, 'absolute_url'):
            base_url = context.absolute_url()
        else:
            base_url = req.base_url()
    else:
        base_url = None
    try:
        pub = CWReSTPublisher(context, settings,
                              parser=CubicWebReSTParser(),
                              writer=Writer(base_url=base_url),
                              source_class=io.StringInput,
                              destination_class=io.StringOutput)
        pub.set_source(data)
        pub.set_destination()
        res = pub.publish(enable_exit_status=None)
        # necessary for proper garbage collection, else a ref is kept somewhere in docutils...
        del pub.settings.context
        return res
    except Exception:
        LOGGER.exception('error while publishing ReST text')
        if not isinstance(data, unicode):
            data = unicode(data, encoding, 'replace')
        return xml_escape(req._('error while publishing ReST text')
                           + '\n\n' + data)


_INITIALIZED = False
def cw_rest_init():
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True
    register_canonical_role('eid', eid_reference_role)
    directives.register_directive('winclude', winclude_directive)
    if pygments_directive is not None:
        directives.register_directive('sourcecode', pygments_directive)
