"""provides simpleTAL extensions for CubicWeb

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

__docformat__ = "restructuredtext en"

import sys
import re
from os.path import exists, isdir, join
from logging import getLogger
from StringIO import StringIO

from simpletal import simpleTAL, simpleTALES

from logilab.common.decorators import cached

LOGGER = getLogger('cubicweb.tal')


class LoggerAdapter(object):
    def __init__(self, tal_logger):
        self.tal_logger = tal_logger

    def debug(self, msg):
        LOGGER.debug(msg)

    def warn(self, msg):
        LOGGER.warning(msg)

    def __getattr__(self, attrname):
        return getattr(self.tal_logger, attrname)


class CubicWebContext(simpleTALES.Context):
    """add facilities to access entity / resultset"""

    def __init__(self, options=None, allowPythonPath=1):
        simpleTALES.Context.__init__(self, options, allowPythonPath)
        self.log = LoggerAdapter(self.log)

    def update(self, context):
        for varname, value in context.items():
            self.addGlobal(varname, value)

    def addRepeat(self, name, var, initialValue):
        simpleTALES.Context.addRepeat(self, name, var, initialValue)

# XXX FIXME need to find a clean to define OPCODE values for extensions
I18N_CONTENT = 18
I18N_REPLACE = 19
RQL_EXECUTE  = 20
# simpleTAL uses the OPCODE values to define priority over commands.
# TAL_ITER should have the same priority than TAL_REPEAT (i.e. 3), but
# we can't use the same OPCODE for two different commands without changing
# the simpleTAL implementation. Another solution would be to totally override
# the REPEAT implementation with the ITER one, but some specific operations
# (involving len() for instance) are not implemented for ITER, so we prefer
# to keep both implementations for now, and to fool simpleTAL by using a float
# number between 3 and 4
TAL_ITER     = 3.1


# FIX simpleTAL HTML 4.01 stupidity
# (simpleTAL never closes tags like INPUT, IMG, HR ...)
simpleTAL.HTML_FORBIDDEN_ENDTAG.clear()

class CubicWebTemplateCompiler(simpleTAL.HTMLTemplateCompiler):
    """extends default compiler by adding i18n:content commands"""

    def __init__(self):
        simpleTAL.HTMLTemplateCompiler.__init__(self)
        self.commandHandler[I18N_CONTENT] = self.compile_cmd_i18n_content
        self.commandHandler[I18N_REPLACE] = self.compile_cmd_i18n_replace
        self.commandHandler[RQL_EXECUTE] = self.compile_cmd_rql
        self.commandHandler[TAL_ITER] = self.compile_cmd_tal_iter

    def setTALPrefix(self, prefix):
        simpleTAL.TemplateCompiler.setTALPrefix(self, prefix)
        self.tal_attribute_map['i18n:content'] = I18N_CONTENT
        self.tal_attribute_map['i18n:replace'] = I18N_REPLACE
        self.tal_attribute_map['rql:execute'] = RQL_EXECUTE
        self.tal_attribute_map['tal:iter'] = TAL_ITER

    def compile_cmd_i18n_content(self, argument):
        # XXX tal:content structure=, text= should we support this ?
        structure_flag = 0
        return (I18N_CONTENT, (argument, False, structure_flag, self.endTagSymbol))

    def compile_cmd_i18n_replace(self, argument):
        # XXX tal:content structure=, text= should we support this ?
        structure_flag = 0
        return (I18N_CONTENT, (argument, True, structure_flag, self.endTagSymbol))

    def compile_cmd_rql(self, argument):
        return (RQL_EXECUTE, (argument, self.endTagSymbol))

    def compile_cmd_tal_iter(self, argument):
        original_id, (var_name, expression, end_tag_symbol) = \
                     simpleTAL.HTMLTemplateCompiler.compileCmdRepeat(self, argument)
        return (TAL_ITER, (var_name, expression, self.endTagSymbol))

    def getTemplate(self):
        return CubicWebTemplate(self.commandList, self.macroMap, self.symbolLocationTable)

    def compileCmdAttributes (self, argument):
        """XXX modified to support single attribute
        definition ending by a ';'

        backport this to simpleTAL
        """
        # Compile tal:attributes into attribute command
        # Argument: [(attributeName, expression)]

        # Break up the list of attribute settings first
        commandArgs = []
        # We only want to match semi-colons that are not escaped
        argumentSplitter =  re.compile(r'(?<!;);(?!;)')
        for attributeStmt in argumentSplitter.split(argument):
            if not attributeStmt.strip():
                continue
            #  remove any leading space and un-escape any semi-colons
            attributeStmt = attributeStmt.lstrip().replace(';;', ';')
            # Break each attributeStmt into name and expression
            stmtBits = attributeStmt.split(' ')
            if (len (stmtBits) < 2):
                # Error, badly formed attributes command
                msg = "Badly formed attributes command '%s'.  Attributes commands must be of the form: 'name expression[;name expression]'" % argument
                self.log.error(msg)
                raise simpleTAL.TemplateParseException(self.tagAsText(self.currentStartTag), msg)
            attName = stmtBits[0]
            attExpr = " ".join(stmtBits[1:])
            commandArgs.append((attName, attExpr))
        return (simpleTAL.TAL_ATTRIBUTES, commandArgs)


class CubicWebTemplateInterpreter(simpleTAL.TemplateInterpreter):
    """provides implementation for interpreting cubicweb extensions"""
    def __init__(self):
        simpleTAL.TemplateInterpreter.__init__(self)
        self.commandHandler[I18N_CONTENT] = self.cmd_i18n
        self.commandHandler[TAL_ITER] = self.cmdRepeat
        # self.commandHandler[RQL_EXECUTE] = self.cmd_rql

    def cmd_i18n(self, command, args):
        """i18n:content and i18n:replace implementation"""
        string, replace_flag, structure_flag, end_symbol = args
        if replace_flag:
            self.outputTag = 0
        result = self.context.globals['_'](string)
        self.tagContent = (0, result)
        self.movePCForward = self.symbolTable[end_symbol]
        self.programCounter += 1


class CubicWebTemplate(simpleTAL.HTMLTemplate):
    """overrides HTMLTemplate.expand() to systematically use CubicWebInterpreter
    """
    def expand(self, context, outputFile):
        interpreter = CubicWebTemplateInterpreter()
        interpreter.initialise(context, outputFile)
        simpleTAL.HTMLTemplate.expand(self, context, outputFile,# outputEncoding='unicode',
                                      interpreter=interpreter)

    def expandInline(self, context, outputFile, interpreter):
        """ Internally used when expanding a template that is part of a context."""
        try:
            interpreter.execute(self)
        except UnicodeError, unierror:
            LOGGER.exception(str(unierror))
            raise simpleTALES.ContextContentException("found non-unicode %r string in Context!" % unierror.args[1]), None, sys.exc_info()[-1]


def compile_template(template):
    """compiles a TAL template string
    :type template: unicode
    :param template: a TAL-compliant template string
    """
    string_buffer = StringIO(template)
    compiler = CubicWebTemplateCompiler()
    compiler.parseTemplate(string_buffer) # , inputEncoding='unicode')
    return compiler.getTemplate()


def compile_template_file(filepath):
    """compiles a TAL template file
    :type filepath: str
    :param template: path of the file to compile
    """
    fp = file(filepath)
    file_content = unicode(fp.read()) # template file should be pure ASCII
    fp.close()
    return compile_template(file_content)


def evaluatePython (self, expr):
    if not self.allowPythonPath:
        return self.false
    globals = {}
    for name, value in self.globals.items():
        if isinstance (value, simpleTALES.ContextVariable):
            value = value.rawValue()
        globals[name] = value
    globals['path'] = self.pythonPathFuncs.path
    globals['string'] = self.pythonPathFuncs.string
    globals['exists'] = self.pythonPathFuncs.exists
    globals['nocall'] = self.pythonPathFuncs.nocall
    globals['test'] = self.pythonPathFuncs.test
    locals = {}
    for name, value in self.locals.items():
        if (isinstance (value, simpleTALES.ContextVariable)):
            value = value.rawValue()
        locals[name] = value
    # XXX precompile expr will avoid late syntax error
    try:
        result = eval(expr, globals, locals)
    except Exception, ex:
        ex = ex.__class__('in %r: %s' % (expr, ex))
        raise ex, None, sys.exc_info()[-1]
    if (isinstance (result, simpleTALES.ContextVariable)):
        return result.value()
    return result

simpleTALES.Context.evaluatePython = evaluatePython


class talbased(object):
    def __init__(self, filename, write=True):
##         if not osp.isfile(filepath):
##             # print "[tal.py] just for tests..."
##             # get parent frame
##             directory = osp.abspath(osp.dirname(sys._getframe(1).f_globals['__file__']))
##             filepath = osp.join(directory, filepath)
        self.filename = filename
        self.write = write

    def __call__(self, viewfunc):
        def wrapped(instance, *args, **kwargs):
            variables = viewfunc(instance, *args, **kwargs)
            html = instance.tal_render(self._compiled_template(instance), variables)
            if self.write:
                instance.w(html)
            else:
                return html
        return wrapped

    def _compiled_template(self, instance):
        for fileordirectory in instance.config.vregistry_path():
            filepath = join(fileordirectory, self.filename)
            if isdir(fileordirectory) and exists(filepath):
                return compile_template_file(filepath)
        raise Exception('no such template %s' % self.filename)
    _compiled_template = cached(_compiled_template, 0)
