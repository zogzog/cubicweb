"""only for unit tests !"""

from cubicweb.common.view import EntityView

HTML_PAGE = u"""<html>
  <body>
    <h1>Hello World !</h1>
  </body>
</html>
"""

class SimpleView(EntityView):
    id = 'simple'
    accepts = ('Bug',)

    def call(self, **kwargs):
        self.cell_call(0, 0)

    def cell_call(self, row, col):
        self.w(HTML_PAGE)

class RaisingView(EntityView):
    id = 'raising'
    accepts = ('Bug',)

    def cell_call(self, row, col):
        raise ValueError()
