CubicWeb.require('ajax.js');

function removeBookmark(beid) {
    d = asyncRemoteExec('delete_bookmark', beid);
    d.addCallback(function(boxcontent) {
	    reloadComponent('bookmarks_box', '', 'boxes', 'bookmarks_box');
  	document.location.hash = '#header';
 	updateMessage(_("bookmark has been removed"));
    });
}
