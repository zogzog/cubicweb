"""This module provide syntaxe highlight functions"""

from logilab.common.logging_ext import _colorable_terminal

try:
    from pygments import highlight as pygments_highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters.terminal import TerminalFormatter
    has_pygments = True
except ImportError:
    has_pygments = False


def highlight(code, language):
    if not has_pygments:
        return code

    if not _colorable_terminal():
        return code

    return pygments_highlight(code, get_lexer_by_name(language), TerminalFormatter())
