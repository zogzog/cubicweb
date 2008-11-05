# custom application views

from mx.DateTime import DateTime

from cubicweb.web.views import baseviews
from cubicweb.web.views.boxes import BoxTemplate
from cubicweb.web.views.calendar import MONTHNAMES
from cubicweb.web.htmlwidgets import BoxLink, BoxWidget

_ = unicode


class BlogEntryPrimaryView(baseviews.PrimaryView):
    accepts = ('BlogEntry',)
    
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(u'<h1>%s</h1>' % entity.dc_title())
        entity.view('metadata', w=self.w)
        self.w(entity.printable_value('text'))
        

class BlogArchiveBox(BoxTemplate):
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
            firstday = DateTime(year, month, 1)
            lastday = DateTime(year, month, firstday.days_in_month)
            rql = ('Any B WHERE B is BlogEntry, B creation_date >= "%s", B creation_date <= "%s"'
                   % (firstday.strftime('%Y-%m-%d'), lastday.strftime('%Y-%m-%d')))
            url = self.build_url(rql=rql)
            label = u'%s %s' % (_(MONTHNAMES[month-1]), year)
            box.append( BoxLink(url, label) )
        box.render(self.w)




