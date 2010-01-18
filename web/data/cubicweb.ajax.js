/*
 *  :organization: Logilab
 *  :copyright: 2003-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

CubicWeb.require('python.js');
CubicWeb.require('htmlhelpers.js');

var JSON_BASE_URL = baseuri() + 'json?';

function _loadAjaxHtmlHead(node, head, tag, srcattr) {
    var loaded = [];
    var jqtagfilter = tag + '[' + srcattr + ']';
    jQuery('head ' + jqtagfilter).each(function(i) {
        loaded.push(this.getAttribute(srcattr));
    });
    node.find(tag).each(function(i) {
        if (this.getAttribute(srcattr)) {
            if (!loaded.contains(this.getAttribute(srcattr))) {
                jQuery(this).appendTo(head);
            }
        } else {
            jQuery(this).appendTo(head);
        }
    });
    node.find(jqtagfilter).remove();
}

/*
 * inspect dom response (as returned by getDomFromResponse), search for
 * a <div class="ajaxHtmlHead"> node and put its content into the real
 * document's head.
 * This enables dynamic css and js loading and is used by replacePageChunk
 */
function loadAjaxHtmlHead(response) {
    var $head = jQuery('head');
    var $responseHead = jQuery(response).find('div.ajaxHtmlHead');
    // no ajaxHtmlHead found, no processing required
    if (!$responseHead.length) {
        return response;
    }
    _loadAjaxHtmlHead($responseHead, $head, 'script', 'src');
    _loadAjaxHtmlHead($responseHead, $head, 'link', 'href');
    // add any remaining children (e.g. meta)
    $responseHead.children().appendTo($head);
    // remove original container, which is now empty
    $responseHead.remove();
    // if there was only one actual node in the reponse besides
    // the ajaxHtmlHead, then remove the wrapper created by
    // getDomFromResponse() and return this single element
    // For instance :
    // 1/ CW returned the following content :
    //    <div>the-actual-content</div><div class="ajaxHtmlHead">...</div>
    // 2/ getDomFromReponse() wrapped this into a single DIV to hold everything
    //    in one, unique, dom element
    // 3/ now that we've removed the ajaxHtmlHead div, the only
    //    node left in the wrapper if the 'real' node built by the view,
    //    we can safely return this node. Otherwise, the view itself
    //    returned several 'root' nodes and we need to keep the wrapper
    //    created by getDomFromResponse()
    if (response.childNodes.length == 1 &&
	response.getAttribute('cubicweb:type') == 'cwResponseWrapper') {
        return response.firstChild;
    }
    return response;
}

function preprocessAjaxLoad(node, newdomnode) {
    return loadAjaxHtmlHead(newdomnode);
}

function postAjaxLoad(node) {
    // find sortable tables if there are some
    if (typeof(Sortable) != 'undefined') {
        Sortable.sortTables(node);
    }
    // find textareas and wrap them if there are some
    if (typeof(FCKeditor) != 'undefined') {
        buildWysiwygEditors();
    }
    if (typeof initFacetBoxEvents != 'undefined') {
        initFacetBoxEvents(node);
    }
    if (typeof buildWidgets != 'undefined') {
        buildWidgets(node);
    }
    if (typeof roundedCorners != 'undefined') {
        roundedCorners(node);
    }
    if (typeof setFormsTarget != 'undefined') {
       setFormsTarget(node);
    }
    loadDynamicFragments(node);
    // XXX simulates document.ready, but the former
    // only runs once, this one potentially many times
    // we probably need to unbind the fired events
    // When this is done, jquery.treeview.js (for instance)
    // can be unpatched.
    jQuery(CubicWeb).trigger('ajax-loaded');
}

/* cubicweb loadxhtml plugin to make jquery handle xhtml response
 *
 * fetches `url` and replaces this's content with the result
 *
 * @param mode how the replacement should be done (default is 'replace')
 *  Possible values are :
 *    - 'replace' to replace the node's content with the generated HTML
 *    - 'swap' to replace the node itself with the generated HTML
 *    - 'append' to append the generated HTML to the node's content
 */
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
    var node = this.get(0); // only consider the first element
    mode = mode || 'replace';
    var callback = null;
    if (data && data.callback) {
        callback = data.callback;
        delete data.callback;
    }
    ajax(url, data, function(response) {
        var domnode = getDomFromResponse(response);
        domnode = preprocessAjaxLoad(node, domnode);
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
        postAjaxLoad(node);
        while (jQuery.isFunction(callback)) {
            callback = callback.apply(this, [domnode]);
        }
    });
};



/* finds each dynamic fragment in the page and executes the
 * the associated RQL to build them (Async call)
 */
function loadDynamicFragments(node) {
    if (node) {
        var fragments = jQuery(node).find('div.dynamicFragment');
    } else {
        var fragments = jQuery('div.dynamicFragment');
    }
    if (fragments.length == 0) {
        return;
    }
    if (typeof LOADING_MSG == 'undefined') {
        LOADING_MSG = 'loading'; // this is only a safety belt, it should not happen
    }
    for(var i=0; i<fragments.length; i++) {
        var fragment = fragments[i];
        fragment.innerHTML = '<h3>' + LOADING_MSG + ' ... <img src="data/loading.gif" /></h3>';
        // if cubicweb:loadurl is set, just pick the url et send it to loadxhtml
        var url = getNodeAttribute(fragment, 'cubicweb:loadurl');
        if (url) {
            jQuery(fragment).loadxhtml(url);
            continue;
        }
        // else: rebuild full url by fetching cubicweb:rql, cubicweb:vid, etc.
        var rql = getNodeAttribute(fragment, 'cubicweb:rql');
        var items = getNodeAttribute(fragment, 'cubicweb:vid').split('&');
        var vid = items[0];
        var extraparams = {};
        // case where vid='myvid&param1=val1&param2=val2': this is a deprecated abuse-case
        if (items.length > 1) {
            console.log("[3.5] you're using extraargs in cubicweb:vid attribute, this is deprecated, consider using loadurl instead");
            for (var j=1; j<items.length; j++) {
                var keyvalue = items[j].split('=');
                extraparams[keyvalue[0]] = keyvalue[1];
            }
        }
        var actrql = getNodeAttribute(fragment, 'cubicweb:actualrql');
        if (actrql) { extraparams['actualrql'] = actrql; }
        var fbvid = getNodeAttribute(fragment, 'cubicweb:fallbackvid');
        if (fbvid) { extraparams['fallbackvid'] = fbvid; }
        replacePageChunk(fragment.id, rql, vid, extraparams);
    }
}

jQuery(document).ready(function() {loadDynamicFragments();});

//============= base AJAX functions to make remote calls =====================//

function remoteCallFailed(err, req) {
    if (req.status == 500) {
        updateMessage(err);
    } else {
        updateMessage(_("an error occured while processing your request"));
    }
}


/*
 * This function will call **synchronously** a remote method on the cubicweb server
 * @param fname: the function name to call (as exposed by the JSONController)
 *
 * additional arguments will be directly passed to the specified function
 *
 * It looks at http headers to guess the response type.
 */
function remoteExec(fname /* ... */) {
    setProgressCursor();
    var props = {'fname' : fname, 'pageid' : pageid,
                      'arg': map(jQuery.toJSON, sliceList(arguments, 1))};
    var result  = jQuery.ajax({url: JSON_BASE_URL, data: props, async: false}).responseText;
    if (result) {
        result = evalJSON(result);
    }
    resetCursor();
    return result;
}

/*
 * This function will call **asynchronously** a remote method on the json
 * controller of the cubicweb http server
 *
 * @param fname: the function name to call (as exposed by the JSONController)
 *
 * additional arguments will be directly passed to the specified function
 *
 * It looks at http headers to guess the response type.
 */

function asyncRemoteExec(fname /* ... */) {
    setProgressCursor();
    var props = {'fname' : fname, 'pageid' : pageid,
                      'arg': map(jQuery.toJSON, sliceList(arguments, 1))};
    var deferred = loadRemote(JSON_BASE_URL, props, 'POST');
    deferred = deferred.addErrback(remoteCallFailed);
    deferred = deferred.addErrback(resetCursor);
    deferred = deferred.addCallback(resetCursor);
    return deferred;
}


/* emulation of gettext's _ shortcut
 */
function _(message) {
    return remoteExec('i18n', [message])[0];
}

function userCallback(cbname) {
    asyncRemoteExec('user_callback', cbname);
}

function unloadPageData() {
    // NOTE: do not make async calls on unload if you want to avoid
    //       strange bugs
    remoteExec('unload_page_data');
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
    var d = asyncRemoteExec('component', compid, rql, registry, extraargs);
    d.addCallback(function(result, req) {
        var domnode = getDomFromResponse(result);
        if (node) {
            // make sure the component is visible
            removeElementClass(node, "hidden");
            swapDOM(node, domnode);
            postAjaxLoad(domnode);
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
    return reloadComponent(boxid, rql, 'boxes', boxid);
}

function userCallbackThenUpdateUI(cbname, compid, rql, msg, registry, nodeid) {
    var d = asyncRemoteExec('user_callback', cbname);
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
    var d = asyncRemoteExec('user_callback', cbname);
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
    var d = asyncRemoteExec('unregister_user_callback', cbname);
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
        props['fname'] = 'view';
        props['pageid'] = pageid;
        if (vid) { props['vid'] = vid; }
        if (extraparams) { jQuery.extend(props, extraparams); }
        // FIXME we need to do asURL(props) manually instead of
        // passing `props` directly to loadxml because replacePageChunk
        // is sometimes called (abusively) with some extra parameters in `vid`
        var mode = swap?'swap':'replace';
        var url = JSON_BASE_URL + asURL(props);
        jQuery(node).loadxhtml(url, params, 'get', mode);
    } else {
        log('Node', nodeId, 'not found');
    }
}

/* XXX deprecates?
 * fetches `url` and replaces `nodeid`'s content with the result
 * @param replacemode how the replacement should be done (default is 'replace')
 *  Possible values are :
 *    - 'replace' to replace the node's content with the generated HTML
 *    - 'swap' to replace the node itself with the generated HTML
 *    - 'append' to append the generated HTML to the node's content
 */
function loadxhtml(nodeid, url, /* ... */ replacemode) {
    jQuery('#' + nodeid).loadxhtml(url, null, 'post', replacemode);
}

/* XXX: this function should go in edition.js but as for now, htmlReplace
 * references it.
 *
 * replace all textareas with fckeditors.
 */
function buildWysiwygEditors(parent) {
    jQuery('textarea').each(function () {
        if (this.getAttribute('cubicweb:type') == 'wysiwyg') {
            // mark editor as instanciated, we may be called a number of times
            // (see postAjaxLoad)
            this.setAttribute('cubicweb:type', 'fckeditor');
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


/*
 * takes a list of DOM nodes and removes all empty text nodes
 */
function stripEmptyTextNodes(nodelist) {
    /* this DROPS empty text nodes */
    var stripped = [];
    for (var i=0; i < nodelist.length; i++) {
        var node = nodelist[i];
        if (isTextNode(node)) {
             /* all browsers but FF -> innerText, FF -> textContent  */
             var text = node.innerText || node.textContent;
             if (text && !text.strip()) {
               continue;
             }
        } else {
            stripped.push(node);
        }
    }
    return stripped;
}

/* convenience function that returns a DOM node based on req's result.
 * XXX clarify the need to clone
 * */
function getDomFromResponse(response) {
    if (typeof(response) == 'string') {
        var doc = html2dom(response);
    } else {
        var doc = response.documentElement;
    }
    var children = doc.childNodes;
    if (!children.length) {
        // no child (error cases) => return the whole document
        return jQuery(doc).clone().context;
    }
    children = stripEmptyTextNodes(children);
    if (children.length == 1) {
        // only one child => return it
        return jQuery(children[0]).clone().context;
    }
    // several children => wrap them in a single node and return the wrap
    return DIV({'cubicweb:type': "cwResponseWrapper"},
               map(function(node) {
                    return jQuery(node).clone().context;
            }, children));
}

function postJSON(url, data, callback) {
    return jQuery.post(url, data, callback, 'json');
}

function getJSON(url, data, callback){
    return jQuery.get(url, data, callback, 'json');
}

CubicWeb.provide('ajax.js');
