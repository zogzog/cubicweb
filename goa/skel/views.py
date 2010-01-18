# custom application views
"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from datetime import date

from cubicweb.utils import last_day
from cubicweb.web.views import baseviews, boxes, calendar
from cubicweb.web.htmlwidgets import BoxLink, BoxWidget

_ = unicode


class BlogEntryPrimaryView(baseviews.PrimaryView):
    accepts = ('BlogEntry',)

    def cell_call(self, row, col):
        entity = self.rset.get_entity(row, col)
        self.w(u'<h1>%s</h1>' % entity.dc_title())
        entity.view('metadata', w=self.w)
        self.w(entity.printable_value('text'))


class BlogArchiveBox(boxes.BoxTemplate):
    """side box usually displaying some related entities in a primary view"""
    id = 'blog_archives_box'
    title = _('blog archives')

    def call(self, **kwargs):
        """display a list of entities by calling their <item_vid> view
        """
        _ = self.req._
        rset = self.req.execute('Any CD ORDERBY CD DESC WHERE B is Blog, B creation_date CD')
        blogmonths = []
        for (blogdate,) in rset:
            year, month = blogdate.year, blogdate.month
            if (year, month) not in blogmonths:
                blogmonths.append( (year, month) )
        box = BoxWidget(_('Blog archives'), id=self.id)
        for year, month in blogmonths:
            firstday = date(year, month, 1)
            lastday = last_day(firstday)
            rql = ('Any B WHERE B is BlogEntry, B creation_date >= "%s", B creation_date <= "%s"'
                   % (firstday.strftime('%Y-%m-%d'), lastday.strftime('%Y-%m-%d')))
            url = self.build_url(rql=rql)
            label = u'%s %s' % (_(calendar.MONTHNAMES[month-1]), year)
            box.append( BoxLink(url, label) )
        box.render(self.w)




