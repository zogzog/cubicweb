"""This module provide syntaxe highlight functions"""

from logilab.common.logging_ext import _colorable_terminal

try:
    from pygments import highlight as pygments_highlight
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters.terminal import TerminalFormatter
    from pygments.formatters.html import HtmlFormatter
    has_pygments = True
except ImportError:
    has_pygments = False


def highlight_terminal(code, language):
    if not has_pygments:
        return code

    if not _colorable_terminal():
        return code

    return pygments_highlight(code, get_lexer_by_name(language), TerminalFormatter())


def highlight_html(code, language, linenos=False, linenostart=1, **kwargs):
    if not has_pygments:
        return str(code)

    return pygments_highlight(str(code),
                              get_lexer_by_name(language),
                              HtmlFormatter(wrapcode=True, linenos=linenos, linenostart=linenostart, **kwargs))


def generate_css():
    if has_pygments:
        return HtmlFormatter().get_style_defs()
    else:
        return ""
