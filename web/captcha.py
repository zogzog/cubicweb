"""Simple captcha library, based on PIL. Monkey patch functions in this module
if you want something better...

:organization: Logilab
:copyright: 2009-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from random import randint, choice
from cStringIO import StringIO

import Image, ImageFont, ImageDraw, ImageFilter


from time import time

from cubicweb import tags
from cubicweb.web import formwidgets as fw


def pil_captcha(text, fontfile, fontsize):
    """Generate a captcha image. Return a PIL image object.

    adapted from http://code.activestate.com/recipes/440588/
    """
    # randomly select the foreground color
    fgcolor = randint(0, 0xffff00)
    # make the background color the opposite of fgcolor
    bgcolor = fgcolor ^ 0xffffff
    # create a font object
    font = ImageFont.truetype(fontfile, fontsize)
    # determine dimensions of the text
    dim = font.getsize(text)
    # create a new image slightly larger that the text
    img = Image.new('RGB', (dim[0]+5, dim[1]+5), bgcolor)
    draw = ImageDraw.Draw(img)
    # draw 100 random colored boxes on the background
    x, y = img.size
    for num in xrange(100):
        draw.rectangle((randint(0, x), randint(0, y),
                        randint(0, x), randint(0, y)),
                       fill=randint(0, 0xffffff))
    # add the text to the image
    draw.text((3, 3), text, font=font, fill=fgcolor)
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    return img


def captcha(fontfile, fontsize, size=5, format='JPEG'):
    """Generate an arbitrary text, return it together with a buffer containing
    the captcha image for the text
    """
    text = u''.join(choice('QWERTYUOPASDFGHJKLZXCVBNM') for i in range(size))
    img = pil_captcha(text, fontfile, fontsize)
    out = StringIO()
    img.save(out, format)
    out.seek(0)
    return text, out


class CaptchaWidget(fw.TextInput):
    def render(self, form, field, renderer=None):
        # t=int(time()*100) to make sure img is not cached
        src = form._cw.build_url('view', vid='captcha', t=int(time()*100))
        img = tags.img(src=src, alt=u'captcha')
        img = u'<div class="captcha">%s</div>' % img
        return img + super(CaptchaWidget, self).render(form, field, renderer)
