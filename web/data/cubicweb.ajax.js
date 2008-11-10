/*
 *  :organization: Logilab
 *  :copyright: 2003-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

CubicWeb.require('python.js');
CubicWeb.require('htmlhelpers.js');

var JSON_BASE_URL = baseuri() + 'json?';

// cubicweb loadxhtml plugin to make jquery handle xhtml response
jQuery.fn.loadxhtml = function(url, data, reqtype, mode) {
    var ajax = null;
    if (reqtype == 'post') {
	ajax = jQuery.post;
    } else {
	ajax = jQuery.get;
    }
    if (this.size() > 1) {
	log('loadxhtml was called with more than one element');
    }
    mode = mode || 'replace';
    var callback = null;
    if (data && data.callback) {
	callback = data.callback;
	delete data.callback;
    }
    var node = this.get(0); // only consider the first element
    ajax(url, data, function(response) {
	var domnode = getDomFromResponse(response);
	if (mode == 'swap') {
	    var origId = node.id;
	    node = swapDOM(node, domnode);
	    if (!node.id) {
		node.id = origId;
	    }
	} else if (mode == 'replace') {
	    jQuery(node).empty().append(domnode);
	} else if (mode == 'append') {
	    jQuery(node).append(domnode);
	}
	// find sortable tables if there are some
	if (typeof(Sortable) != 'undefined') {
	    Sortable.sortTables(node);
	}
	// find textareas and wrap them if there are some
	if (typeof(FCKeditor) != 'undefined') {
	    buildWysiwygEditors(node);
	}

	if (typeof initFacetBoxEvents != 'undefined') {
	    initFacetBoxEvents(node);
	}

	if (typeof buildWidgets != 'undefined') {
	    buildWidgets(node);
	}

	while (jQuery.isFunction(callback)) {
	    callback = callback.apply(this, [domnode]);
	}
    });
}



/* finds each dynamic fragment in the page and executes the
 * the associated RQL to build them (Async call)
 */
function loadDynamicFragments() {
    var fragments = getElementsByTagAndClassName('div', 'dynamicFragment');
    if (fragments.length == 0) {
	return;
    }
    if (typeof LOADING_MSG == 'undefined') {
	LOADING_MSG = 'loading'; // this is only a safety belt, it should not happen
    }
    for(var i=0; i<fragments.length; i++) {
	var fragment = fragments[i];
	fragment.innerHTML = '<h3>' + LOADING_MSG + ' ... <img src="data/loading.gif" /></h3>';
	var rql = getNodeAttribute(fragment, 'cubicweb:rql');
	var vid = getNodeAttribute(fragment, 'cubicweb:vid');
        var extraparams = {};
	var actrql = getNodeAttribute(fragment, 'cubicweb:actualrql');
	if (actrql) { extraparams['actualrql'] = actrql; }
	var fbvid = getNodeAttribute(fragment, 'cubicweb:fallbackvid');
	if (fbvid) { extraparams['fallbackvid'] = fbvid; }

	replacePageChunk(fragment.id, rql, vid, extraparams);
    }
}

jQuery(document).ready(loadDynamicFragments);

//============= base AJAX functions to make remote calls =====================//


/*
 * This function will call **synchronously** a remote method on the cubicweb server
 * @param fname: the function name to call (as exposed by the JSONController)
 * @param args: the list of arguments to pass the function
 */
function remote_exec(fname) {
    setProgressCursor();
    var props = {'mode' : "remote", 'fname' : fname, 'pageid' : pageid,
     		 'arg': map(jQuery.toJSON, sliceList(arguments, 1))};
    var result  = jQuery.ajax({url: JSON_BASE_URL, data: props, async: false}).responseText;
    result = evalJSON(result);
    resetCursor();
    return result;
}

function remoteCallFailed(err, req) {
    if (req.status == 500) {
	updateMessage(err);
    } else {
	updateMessage(_("an error occured while processing your request"));
    }
}

/*
 * This function is the equivalent of MochiKit's loadJSONDoc but
 * uses POST instead of GET
 */
function loadJSONDocUsingPOST(url, queryargs, mode) {
    mode = mode || 'remote';
    setProgressCursor();
    var dataType = (mode == 'remote') ? "json":null;
    var deferred = loadJSON(url, queryargs, 'POST', dataType);
    deferred = deferred.addErrback(remoteCallFailed);
//     if (mode == 'remote') {
// 	deferred = deferred.addCallbacks(evalJSONRequest);
//     }
    deferred = deferred.addCallback(resetCursor);
    return deferred;
}


function _buildRemoteArgs(fname) {
    return  {'mode' : "remote", 'fname' : fname, 'pageid' : pageid,
     	     'arg': map(jQuery.toJSON, sliceList(arguments, 1))};
}

/*
 * This function will call **asynchronously** a remote method on the cubicweb server
 * This function is a low level one. You should use `async_remote_exec` or
 * `async_rawremote_exec` instead.
 *
 * @param fname: the function name to call (as exposed by the JSONController)
 * @param funcargs: the function's arguments
 * @param mode: rawremote or remote
 */
function _async_exec(fname, funcargs, mode) {
    setProgressCursor();
    var props = {'mode' : mode, 'fname' : fname, 'pageid' : pageid};
    var args = map(urlEncode, map(jQuery.toJSON, funcargs));
    args.unshift(''); // this is to be able to use join() directly
    var queryargs = as_url(props) + args.join('&arg=');
    return loadJSONDocUsingPOST(JSON_BASE_URL, queryargs, mode);
}

/*
 * This function will call **asynchronously** a remote method on the cubicweb server
 * @param fname: the function name to call (as exposed by the JSONController)
 * additional arguments will be directly passed to the specified function
 * Expected response type is Json.
 */
function async_remote_exec(fname /* ... */) {
    return _async_exec(fname, sliceList(arguments, 1), 'remote');
}

/*
 * This version of _async_exec doesn't expect a json response.
 * It looks at http headers to guess the response type.
 */
function async_rawremote_exec(fname /* ... */) {
    return _async_exec(fname, sliceList(arguments, 1), 'rawremote');
}

/*
 * This function will call **asynchronously** a remote method on the cubicweb server
 * @param fname: the function name to call (as exposed by the JSONController)
 * @param varargs: the list of arguments to pass to the function
 * This is an alternative form of `async_remote_exec` provided for convenience
 */
function async_remote_exec_varargs(fname, varargs) {
    return _async_exec(fname, varargs, 'remote');
}

/* emulation of gettext's _ shortcut
 */
function _(message) {
    return remote_exec('i18n', [message])[0];
}

function rqlexec(rql) {
    return async_remote_exec('rql', rql);
}

function userCallback(cbname) {
    async_remote_exec('user_callback', cbname);
}

function unloadPageData() {
    // NOTE: do not make async calls on unload if you want to avoid
    //       strange bugs
    remote_exec('unload_page_data');
}

function openHash() {
    if (document.location.hash) {
	var nid = document.location.hash.replace('#', '');
	var node = jQuery('#' + nid);
	if (node) { removeElementClass(node, "hidden"); }
    };
}
jQuery(document).ready(openHash);

function reloadComponent(compid, rql, registry, nodeid, extraargs) {
    registry = registry || 'components';
    rql = rql || '';
    nodeid = nodeid || (compid + 'Component');
    extraargs = extraargs || {};
    var node = getNode(nodeid);
    var d = async_rawremote_exec('component', compid, rql, registry, extraargs);
    d.addCallback(function(result, req) {
	var domnode = getDomFromResponse(result);
	if (node) {
	    // make sure the component is visible
	    removeElementClass(node, "hidden");
	    swapDOM(node, domnode);
	}
    });
    d.addCallback(resetCursor);
    d.addErrback(function(xxx) {
	updateMessage(_("an error occured"));
	log(xxx);
    });
  return d;
}

/* XXX: HTML architecture of cubicweb boxes is a bit strange */
function reloadBox(boxid, rql) {
    reloadComponent(boxid, rql, 'boxes', boxid);
}

function userCallbackThenUpdateUI(cbname, compid, rql, msg, registry, nodeid) {
    var d = async_remote_exec('user_callback', cbname);
    d.addCallback(function() {
	reloadComponent(compid, rql, registry, nodeid);
	if (msg) { updateMessage(msg); }
    });
    d.addCallback(resetCursor);
    d.addErrback(function(xxx) {
	updateMessage(_("an error occured"));
	log(xxx);
	return resetCursor();
    });
}

function userCallbackThenReloadPage(cbname, msg) {
    var d = async_remote_exec('user_callback', cbname);
    d.addCallback(function() {
	window.location.reload();
	if (msg) { updateMessage(msg); }
    });
    d.addCallback(resetCursor);
    d.addErrback(function(xxx) {
	updateMessage(_("an error occured"));
	log(xxx);
	return resetCursor();
    });
}

/*
 * unregisters the python function registered on the server's side
 * while the page was generated.
 */
function unregisterUserCallback(cbname) {
    d = async_remote_exec('unregister_user_callback', cbname);
    d.addCallback(function() {resetCursor();});
    d.addErrback(function(xxx) {
	updateMessage(_("an error occured"));
	log(xxx);
	return resetCursor();
    });
}


/* executes an async query to the server and replaces a node's
 * content with the query result
 *
 * @param nodeId the placeholder node's id
 * @param rql the RQL query
 * @param vid the vid to apply to the RQL selection (default if not specified)
 * @param extraparmas table of additional query parameters
 */
function replacePageChunk(nodeId, rql, vid, extraparams, /* ... */ swap, callback) {
    var params = null;
    if (callback) {
	params = {callback: callback};
    }

    var node = jQuery('#' + nodeId)[0];
    var props = {};
    if (node) {
	props['rql'] = rql;
	props['pageid'] = pageid;
	if (vid) { props['vid'] = vid; }
	if (extraparams) { jQuery.extend(props, extraparams); }
	// FIXME we need to do as_url(props) manually instead of
	// passing `props` directly to loadxml because replacePageChunk
	// is sometimes called (abusively) with some extra parameters in `vid`
	var mode = swap?'swap':'replace';
	var url = JSON_BASE_URL + as_url(props);
	jQuery(node).loadxhtml(url, params, 'get', mode);
    } else {
	log('Node', nodeId, 'not found');
    }
}

/* XXX: this function should go in edition.js but as for now, htmlReplace
 * references it.
 *
 * replace all textareas with fckeditors.
 */
function buildWysiwygEditors(parent) {
    jQuery('textarea').each(function () {
	if (this.getAttribute('cubicweb:type', 'wysiwyg')) {
	    if (typeof FCKeditor != "undefined") {
		var fck = new FCKeditor(this.id);
		fck.Config['CustomConfigurationsPath'] = fckconfigpath;
		fck.Config['DefaultLanguage'] = fcklang;
		fck.BasePath = "fckeditor/";
		fck.ReplaceTextarea();
	    } else {
		log('fckeditor could not be found.');
	    }
	}
    });
}

jQuery(document).ready(buildWysiwygEditors);


/* convenience function that returns a DOM node based on req's result. */
function getDomFromResponse(response) {
    if (typeof(response) == 'string') {
	return html2dom(response);
    }
    var doc = response.documentElement;
    var children = doc.childNodes;
    if (!children.length) {
	// no child (error cases) => return the whole document
	return doc.cloneNode(true);
    }
    if (children.length == 1) {
	// only one child => return it
	return children[0].cloneNode(true);
    }
    // several children => wrap them in a single node and return the wrap
    return DIV(null, map(methodcaller('cloneNode', true), children));
}

function postJSON(url, data, callback) {
    return jQuery.post(url, data, callback, 'json');
}

function getJSON(url, data, callback){
    return jQuery.get(url, data, callback, 'json');
}

CubicWeb.provide('ajax.js');
