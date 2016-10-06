from six import text_type

from cubicweb.pyramid.test import PyramidCWTest
from cubicweb.pyramid import tools


def set_language(request):
    lang = request.POST.get('lang', None)
    cnx = request.cw_cnx
    if lang is None:
        cnx.execute('DELETE CWProperty X WHERE X for_user U, U eid %(u)s',
                    {'u': cnx.user.eid})
    else:
        cnx.user.set_property(u'ui.language', text_type(lang))
    cnx.commit()

    request.response.text = text_type(cnx.user.properties.get('ui.language', ''))
    return request.response


def add_remove_group(request):
    add_remove = request.POST['add_remove']
    cnx = request.cw_cnx
    if add_remove == 'add':
        cnx.execute('SET U in_group G WHERE G name "users", U eid %(u)s',
                    {'u': cnx.user.eid})
    else:
        cnx.execute('DELETE U in_group G WHERE G name "users", U eid %(u)s',
                    {'u': cnx.user.eid})
    cnx.commit()

    request.response.text = text_type(','.join(sorted(cnx.user.groups)))
    return request.response


class SessionSyncHoooksTC(PyramidCWTest):

    def includeme(self, config):
        for view in (set_language, add_remove_group):
            config.add_route(view.__name__, '/' + view.__name__)
            config.add_view(view, route_name=view.__name__)

    def setUp(self):
        super(SessionSyncHoooksTC, self).setUp()
        with self.admin_access.repo_cnx() as cnx:
            self.admin_eid = cnx.user.eid

    def test_sync_props(self):
        # initialize a pyramid session using admin credentials
        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword})
        self.assertEqual(res.status_int, 303)
        # new property
        res = self.webapp.post('/set_language', {'lang': 'fr'})
        self.assertEqual(res.text, 'fr')
        # updated property
        res = self.webapp.post('/set_language', {'lang': 'en'})
        self.assertEqual(res.text, 'en')
        # removed property
        res = self.webapp.post('/set_language')
        self.assertEqual(res.text, '')

    def test_sync_groups(self):
        # initialize a pyramid session using admin credentials
        res = self.webapp.post('/login', {
            '__login': self.admlogin, '__password': self.admpassword})
        self.assertEqual(res.status_int, 303)
        # XXX how to get pyramid request using this session?
        res = self.webapp.post('/add_remove_group', {'add_remove': 'add'})
        self.assertEqual(res.text, 'managers,users')
        res = self.webapp.post('/add_remove_group', {'add_remove': 'remove'})
        self.assertEqual(res.text, 'managers')


if __name__ == '__main__':
    from unittest import main
    main()
