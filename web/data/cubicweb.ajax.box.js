/**
 * Functions for ajax boxes.
 *
 *  :organization: Logilab
 *  :copyright: 2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 */

function ajaxBoxValidateSelectorInput(boxid, eid, separator, fname, msg) {
    var holderid = cw.utils.domid(boxid) + eid + 'Holder';
    var value = $('#' + holderid + 'Input').val();
    if (separator) {
        value = $.map(value.split(separator), jQuery.trim);
    }
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs(fname, null, eid, value));
    d.addCallback(function() {
            $('#' + holderid).empty();
            var formparams = ajaxFuncArgs('render', null, 'ctxcomponents', boxid, eid);
            $('#' + cw.utils.domid(boxid) + eid).loadxhtml(AJAX_BASE_URL, formparams, null, 'swap');
            if (msg) {
                document.location.hash = '#header';
                updateMessage(msg);
            }
        });
}

function ajaxBoxRemoveLinkedEntity(boxid, eid, relatedeid, delfname, msg) {
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs(delfname, null, eid, relatedeid));
    d.addCallback(function() {
            var formparams = ajaxFuncArgs('render', null, 'ctxcomponents', boxid, eid);
            $('#' + cw.utils.domid(boxid) + eid).loadxhtml(AJAX_BASE_URL, formparams, null, 'swap');
            if (msg) {
                document.location.hash = '#header';
                updateMessage(msg);
            }
    });
}

/**
 * .. function:: ajaxBoxShowSelector(boxid, eid, unrelfname,
 *                                  addfname, msg,
 *                                  oklabel, cancellabel,
 *                                  separator=None)
 *
 * Display an ajax selector within a box of regid `boxid`, for entity with eid
 * `eid`.
 *
 * Other parameters are:
 *
 * * `addfname`, name of the json controller method to call to add a relation
 *
 * * `msg`, message to display to the user when a relation has been added
 *
 * * `oklabel`/`cancellabel`, OK/cancel buttons label
 *
 * * `separator`, items separator if the field is multi-valued (will be
 *   considered mono-valued when not specified)
 */
function ajaxBoxShowSelector(boxid, eid,
                             unrelfname,
                             addfname, msg,
                             oklabel, cancellabel,
                             separator) {
    var holderid = cw.utils.domid(boxid) + eid + 'Holder';
    var holder = $('#' + holderid);
    if (holder.children().length) {
        holder.empty();
    }
    else {
        var inputid = holderid + 'Input';
        var deferred = loadRemote(AJAX_BASE_URL, ajaxFuncArgs(unrelfname, null, eid));
        deferred.addCallback(function (unrelated) {
            var input = INPUT({'type': 'text', 'id': inputid, 'size': 20});
            holder.append(input).show();
            var $input = $(input);
            $input.keypress(function (evt) {
                if (evt.keyCode == $.ui.keyCode.ENTER) {
                    ajaxBoxValidateSelectorInput(boxid, eid, separator, addfname, msg);
                }
            });
            $input.cwautocomplete(unrelated, {multiple: Boolean(separator)});
            var buttons = DIV({'class' : "sgformbuttons"},
                              A({href : "javascript: $.noop();",
                                 onclick : cw.utils.strFuncCall('ajaxBoxValidateSelectorInput',
                                                                boxid, eid, separator, addfname, msg)},
                                oklabel),
                              ' / ',
                              A({'href' : "javascript: $.noop();",
                                 'onclick' : '$("#' + holderid + '").empty()'},
                                  cancellabel));
            holder.append(buttons);
            $input.focus();
        });
    }
}
