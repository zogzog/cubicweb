# -*- coding: utf-8 -*-
import os
os.environ["DJANGO_SETTINGS_MODULE"] = 'data.settings'

from django import template


def encode_output(self, output):
    # Check type so that we don't run str() on a Unicode object
    if not isinstance(output, basestring):
        return unicode(output)
    return output

template.VariableNode.encode_output = encode_output

from cubicweb.common.view import StartupView

INDEX_TEMPLATE = template.Template(u'''
 <h1>hellô {{ user.login }}</h1>
''')

class MyIndex(StartupView):
    id = 'index'

    def call(self):
        ctx = template.Context({'user': self.req.user})
        return INDEX_TEMPLATE.render(ctx)
