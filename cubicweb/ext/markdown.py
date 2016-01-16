from __future__ import absolute_import
import markdown

import logging

log = logging.getLogger(__name__)


def markdown_publish(context, data):
    """publish a string formatted as MarkDown Text to HTML

    :type context: a cubicweb application object

    :type data: str
    :param data: some MarkDown text

    :rtype: unicode
    :return:
      the data formatted as HTML or the original data if an error occurred
    """
    md = markdown.Markdown()
    try:
        return md.convert(data)
    except:
        import traceback; traceback.print_exc()
        log.exception("Error while converting Markdown to HTML")
        return data
