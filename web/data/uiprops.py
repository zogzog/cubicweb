"""define default ui properties"""

# CSS stylesheets to include systematically in HTML headers
STYLESHEETS =       [data('cubicweb.reset.css'),
                     data('cubicweb.css')]
STYLESHEETS_IE =    [data('cubicweb.ie.css')]
STYLESHEETS_PRINT = [data('cubicweb.print.css')]

# Javascripts files to include systematically in HTML headers
JAVASCRIPTS = [data('jquery.js'),
               data('jquery.corner.js'),
               data('jquery.json.js'),
               data('cubicweb.compat.js'),
               data('cubicweb.python.js'),
               data('cubicweb.htmlhelpers.js')]

# where is installed fckeditor
FCKEDITOR_PATH = '/usr/share/fckeditor/'

# favicon and logo for the instance
FAVICON = data('favicon.ico')
LOGO = data('logo.png')

# rss logo (link to get the rss view of a selection)
RSS_LOGO = data('rss.png')
RSS_LOGO_16 = data('feed-icon16x16.png')
RSS_LOGO_32 = data('feed-icon32x32.png')

# XXX cleanup resources below, some of them are probably not used
# (at least entity types icons...)

# images
HELP = data('help.png')
SEARCH_GO = data('go.png')
PUCE_UP = data('puce_up.png')
PUCE_DOWN = data('puce_down.png')

# button icons
OK_ICON = data('ok.png')
CANCEL_ICON = data('cancel.png')
APPLY_ICON = data('plus.png')
TRASH_ICON = data('trash_can_small.png')

# icons for entity types
BOOKMARK_ICON = data('icon_bookmark.gif')
EMAILADDRESS_ICON = data('icon_emailaddress.gif')
EUSER_ICON = data('icon_euser.gif')
STATE_ICON = data('icon_state.gif')

# other icons
CALENDAR_ICON = data('calendar.gif')
CANCEL_EMAIL_ICON = data('sendcancel.png')
SEND_EMAIL_ICON = data('sendok.png')
DOWNLOAD_ICON = data('download.gif')
UPLOAD_ICON = data('upload.gif')
GMARKER_ICON = data('gmap_blue_marker.png')
UP_ICON = data('up.gif')
