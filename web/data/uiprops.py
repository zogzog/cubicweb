"""define default ui properties"""

# CSS stylesheets to include systematically in HTML headers
STYLESHEETS =       ['%s/cubicweb.reset.css' % datadir_url,
                     '%s/cubicweb.css' % datadir_url]
STYLESHEETS_IE =    ['%s/cubicweb.ie.css' % datadir_url]
STYLESHEETS_PRINT = ['%s/cubicweb.print.css' % datadir_url]

# Javascripts files to include systematically in HTML headers
JAVASCRIPTS = ['%s/jquery.js' % datadir_url,
               '%s/jquery.corner.js' % datadir_url,
               '%s/jquery.json.js' % datadir_url,
               '%s/cubicweb.compat.js' % datadir_url,
               '%s/cubicweb.python.js' % datadir_url,
               '%s/cubicweb.htmlhelpers.js' % datadir_url]

# where is installed fckeditor
FCKEDITOR_PATH = '/usr/share/fckeditor/'

# favicon and logo for the instance
FAVICON = '%s/favicon.ico' % datadir_url
LOGO = '%s/logo.png' % datadir_url

# rss logo (link to get the rss view of a selection)
RSS_LOGO = '%s/rss.png' % datadir_url
RSS_LOGO_16 = '%s/feed-icon16x16.png' % datadir_url
RSS_LOGO_32 = '%s/feed-icon32x32.png' % datadir_url

# XXX cleanup resources below, some of them are probably not used
# (at least entity types icons...)

# images
HELP = '%s/help.png' % datadir_url
SEARCH_GO = '%s/go.png' % datadir_url
PUCE_UP = '%s/puce_up.png' % datadir_url
PUCE_DOWN = '%s/puce_down.png' % datadir_url

# button icons
OK_ICON = '%s/ok.png' % datadir_url
CANCEL_ICON = '%s/cancel.png' % datadir_url
APPLY_ICON = '%s/plus.png' % datadir_url
TRASH_ICON = '%s/trash_can_small.png' % datadir_url

# icons for entity types
BOOKMARK_ICON = '%s/icon_bookmark.gif' % datadir_url
EMAILADDRESS_ICON = '%s/icon_emailaddress.gif' % datadir_url
EUSER_ICON = '%s/icon_euser.gif' % datadir_url
STATE_ICON = '%s/icon_state.gif' % datadir_url

# other icons
CALENDAR_ICON = '%s/calendar.gif' % datadir_url
CANCEL_EMAIL_ICON = '%s/sendcancel.png' % datadir_url
SEND_EMAIL_ICON = '%s/sendok.png' % datadir_url
DOWNLOAD_ICON = '%s/download.gif' % datadir_url
UPLOAD_ICON = '%s/upload.gif' % datadir_url
GMARKER_ICON = '%s/gmap_blue_marker.png' % datadir_url
UP_ICON = '%s/up.gif' % datadir_url
