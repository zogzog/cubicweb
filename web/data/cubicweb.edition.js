/**
 * Functions dedicated to edition.
 *
 *  :organization: Logilab
 *  :copyright: 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 *
 */

//============= Eproperty form functions =====================================//
/**
 * .. function:: setPropValueWidget(varname, tabindex)
 *
 * called on CWProperty key selection:
 * - get the selected value
 * - get a widget according to the key by a sync query to the server
 * - fill associated div with the returned html
 *
 * * `varname`, the name of the variable as used in the original creation form
 * * `tabindex`, the tabindex that should be set on the widget
 */

function setPropValueWidget(varname, tabindex) {
    var key = firstSelected(document.getElementById('pkey-subject:' + varname));
    if (key) {
        var args = {
            fname: 'prop_widget',
            pageid: pageid,
            arg: $.map([key.value, varname, tabindex], JSON.stringify)
        };
        cw.jqNode('div:value-subject:' + varname).loadxhtml(AJAX_BASE_URL, args, 'post');
    }
}

// *** EDITION FUNCTIONS ****************************************** //
/**
 * .. function:: reorderTabindex(start, formid)
 *
 * this function is called when an AJAX form was generated to
 * make sure tabindex remains consistent
 */
function reorderTabindex(start, formid) {
    var form = cw.getNode(formid || 'entityForm');
    var inputTypes = ['INPUT', 'SELECT', 'TEXTAREA'];
    var tabindex = (start == null) ? 15: start;
    cw.utils.nodeWalkDepthFirst(form, function(elem) {
        var tagName = elem.tagName.toUpperCase();
        if (jQuery.inArray(tagName, inputTypes) != -1) {
            if (jQuery(elem).attr('tabindex') != null) {
                tabindex += 1;
                jQuery(elem).attr('tabindex', tabindex);
            }
            return null;
        }
        return jQuery.grep(elem.childNodes, isElementNode);
    });
}

function showMatchingSelect(selectedValue, eid) {
    if (selectedValue) {
        var divId = 'div' + selectedValue + '_' + eid;
        var divNode = jQuery('#' + divId);
        if (!divNode.length) {
            var args = {
                vid: 'unrelateddivs',
                relation: selectedValue,
                rql: rql_for_eid(eid),
                '__notemplate': 1
            };
            var d = jQuery('#unrelatedDivs_' + eid).loadxhtml(BASE_URL + 'view', args, 'post', 'append');
            d.addCallback(function() {
                _showMatchingSelect(eid, jQuery('#' + divId));
            });
        } else {
            _showMatchingSelect(eid, divNode);
        }
    } else {
        _showMatchingSelect(eid, null);
    }
}

/**
 * .. function:: _showMatchingSelect(eid, divNode)
 *
 * * `divNode`, a jQuery selection
 */
function _showMatchingSelect(eid, divNode) {
    // hide all divs, and then show the matching one
    // (would actually be better to directly hide the displayed one)
    jQuery('#unrelatedDivs_' + eid).children().hide();
    // divNode not found means 'no relation selected' (i.e. first blank item)
    if (divNode && divNode.length) {
        divNode.show();
    }
}

/**
 * .. function:: buildPendingInsertHandle(elementId, element_name, selectNodeId, eid)
 *
 * this function builds a Handle to cancel pending insertion
 */
function buildPendingInsertHandle(elementId, element_name, selectNodeId, eid) {
    jscall = "javascript: cancelPendingInsert('" + [elementId, element_name, selectNodeId, eid].join("', '") + "')";
    return A({
        'class': 'handle',
        'href': jscall,
        'title': _("cancel this insert")
    },
    '[x]');
}

function buildEntityLine(relationName, selectedOptionNode, comboId, eid) {
    // textContent doesn't seem to work on selectedOptionNode
    var content = selectedOptionNode.firstChild.nodeValue;
    var handle = buildPendingInsertHandle(selectedOptionNode.id, 'tr', comboId, eid);
    var link = A({
        'href': 'view?rql=' + selectedOptionNode.value,
        'class': 'editionPending',
        'id': 'a' + selectedOptionNode.id
    },
    content);
    var tr = TR({
        'id': 'tr' + selectedOptionNode.id
    },
    [TH(null, relationName), TD(null, [handle, link])]);
    try {
        var separator = cw.getNode('relationSelectorRow_' + eid);
        //dump('relationSelectorRow_' + eid) XXX warn dump is not implemented in konqueror (at least)
        // XXX Warning: separator.parentNode is not (always ?) the
        // table itself, but an intermediate node (TableSectionElement)
        var tableBody = separator.parentNode;
        tableBody.insertBefore(tr, separator);
    } catch(ex) {
        log("got exception(2)!" + ex);
    }
}

function buildEntityCell(relationName, selectedOptionNode, comboId, eid) {
    var handle = buildPendingInsertHandle(selectedOptionNode.id, 'div_insert_', comboId, eid);
    var link = A({
        'href': 'view?rql=' + selectedOptionNode.value,
        'class': 'editionPending',
        'id': 'a' + selectedOptionNode.id
    },
    content);
    var div = DIV({
        'id': 'div_insert_' + selectedOptionNode.id
    },
    [handle, link]);
    try {
        var td = jQuery('#cell' + relationName + '_' + eid);
        td.appendChild(div);
    } catch(ex) {
        alert("got exception(3)!" + ex);
    }
}

function addPendingInsert(optionNode, eid, cell, relname) {
    var value = jQuery(optionNode).attr('value');
    if (!value) {
        // occurs when the first element in the box is selected (which is not
        // an entity but the combobox title)
        return;
    }
    // 2nd special case
    if (value.indexOf('http') == 0) {
        document.location = value;
        return;
    }
    // add hidden parameter
    var entityForm = jQuery('#entityForm');
    var oid = optionNode.id.substring(2); // option id is prefixed by "id"
    loadRemote(AJAX_BASE_URL, ajaxFuncArgs('add_pending_inserts', null,
                                           [oid.split(':')]), 'GET', true);
    var selectNode = optionNode.parentNode;
    // remove option node
    selectNode.removeChild(optionNode);
    // add line in table
    if (cell) {
        // new relation as a cell in multiple edit
        // var relation_name = relationSelected.getAttribute('value');
        // relation_name = relation_name.slice(0, relation_name.lastIndexOf('_'));
        buildEntityCell(relname, optionNode, selectNode.id, eid);
    }
    else {
        var relationSelector = cw.getNode('relationSelector_' + eid);
        var relationSelected = relationSelector.options[relationSelector.selectedIndex];
        // new relation as a line in simple edit
        buildEntityLine(relationSelected.text, optionNode, selectNode.id, eid);
    }
}

function cancelPendingInsert(elementId, element_name, comboId, eid) {
    // remove matching insert element
    var entityView = cw.jqNode('a' + elementId).text();
    cw.jqNode(element_name + elementId).remove();
    if (comboId) {
        // re-insert option in combobox if it was taken from there
        var selectNode = cw.getNode(comboId);
        // XXX what on object relation
        if (selectNode) {
            var options = selectNode.options;
            var node_id = elementId.substring(0, elementId.indexOf(':'));
            options[options.length] = OPTION({
                'id': elementId,
                'value': node_id
            },
            entityView);
        }
    }
    elementId = elementId.substring(2, elementId.length);
    loadRemote(AJAX_BASE_URL, ajaxFuncArgs('remove_pending_insert', null,
                                           elementId.split(':')), 'GET', true);
}

/**
 * .. function:: buildPendingDeleteHandle(elementId, eid)
 *
 * this function builds a Handle to cancel pending insertion
 */
function buildPendingDeleteHandle(elementId, eid) {
    var jscall = "javascript: addPendingDelete('" + elementId + ', ' + eid + "');";
    return A({
        'href': jscall,
        'class': 'pendingDeleteHandle',
        'title': _("delete this relation")
    },
    '[x]');
}

/**
 * .. function:: addPendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function addPendingDelete(nodeId, eid) {
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs('add_pending_delete', null, nodeId.split(':')));
    d.addCallback(function() {
        // and strike entity view
        cw.jqNode('span' + nodeId).addClass('pendingDelete');
        // replace handle text
        cw.jqNode('handle' + nodeId).text('+');
    });
}

/**
 * .. function:: cancelPendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function cancelPendingDelete(nodeId, eid) {
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs('remove_pending_delete', null, nodeId.split(':')));
    d.addCallback(function() {
        // reset link's CSS class
        cw.jqNode('span' + nodeId).removeClass('pendingDelete');
        // replace handle text
        cw.jqNode('handle' + nodeId).text('x');
    });
}

/**
 * .. function:: togglePendingDelete(nodeId, eid)
 *
 * * `nodeId`, eid_from:r_type:eid_to
 */
function togglePendingDelete(nodeId, eid) {
    // node found means we should cancel deletion
    if (jQuery(cw.getNode('span' + nodeId)).hasClass('pendingDelete')) {
        cancelPendingDelete(nodeId, eid);
    } else {
        addPendingDelete(nodeId, eid);
    }
}

function selectForAssociation(tripletIdsString, originalEid) {
    var tripletlist = $.map(tripletIdsString.split('-'),
                            function(x) { return [x.split(':')] ;});
    var d = loadRemote(AJAX_BASE_URL, ajaxFuncArgs('add_pending_inserts', null, tripletlist));
    d.addCallback(function() {
        var args = {
            vid: 'edition',
            __mode: 'normal',
            rql: rql_for_eid(originalEid)
        };
        document.location = 'view?' + asURL(args);
    });

}

function updateInlinedEntitiesCounters(rtype, role) {
    jQuery('div.inline-' + rtype + '-' + role + '-slot span.icounter').each(function(i) {
        this.innerHTML = i + 1;
    });
}

/**
 * .. function:: addInlineCreationForm(peid, petype, ttype, rtype, role, i18nctx, insertBefore)
 *
 * makes an AJAX request to get an inline-creation view's content
 * * `peid`, the parent entity eid
 *
 * * `petype`, the parent entity type
 *
 * * `ttype`, the target (inlined) entity type
 *
 * * `rtype`, the relation type between both entities
 */
function addInlineCreationForm(peid, petype, ttype, rtype, role, i18nctx, insertBefore) {
    insertBefore = insertBefore || cw.getNode('add' + rtype + ':' + peid + 'link').parentNode;
    var args = ajaxFuncArgs('inline_creation_form', null, peid, petype, ttype, rtype, role, i18nctx);
    var d = loadRemote(AJAX_BASE_URL, args);
    d.addCallback(function(response) {
        var dom = getDomFromResponse(response);
        loadAjaxHtmlHead(dom);
        var form = jQuery(dom);
        form.css('display', 'none');
        form.insertBefore(insertBefore).slideDown('fast');
        updateInlinedEntitiesCounters(rtype, role);
        reorderTabindex(null, $(insertBefore).closest('form')[0]);
        jQuery(cw).trigger('inlinedform-added', form);
        // if the inlined form contains a file input, we must force
        // the form enctype to multipart/form-data
        if (form.find('input:file').length) {
            // NOTE: IE doesn't support dynamic enctype modification, we have
            //       to set encoding too.
            form.closest('form').attr('enctype', 'multipart/form-data').attr('encoding', 'multipart/form-data');
        }
        _postAjaxLoad(dom);
    });
    d.addErrback(function(xxx) {
        cw.log('xxx =', xxx);
    });
}

/**
 * .. function:: removeInlineForm(peid, rtype, role, eid, showaddnewlink)
 *
 * removes the part of the form used to edit an inlined entity
 */
function removeInlineForm(peid, rtype, role, eid, showaddnewlink) {
    cw.jqNode(['div', peid, rtype, eid].join('-')).slideUp('fast', function() {
            $(this).remove();
            updateInlinedEntitiesCounters(rtype, role);
    });
    if (showaddnewlink) {
        toggleVisibility(showaddnewlink);
    }
}

/**
 * .. function:: removeInlinedEntity(peid, rtype, eid)
 *
 * alternatively adds or removes the hidden input that make the
 * edition of the relation `rtype` possible between `peid` and `eid`
 * * `peid`, the parent entity eid
 *
 * * `rtype`, the relation type between both entities
 *
 * * `eid`, the inlined entity eid
 */
function removeInlinedEntity(peid, rtype, eid) {
    // XXX work around the eid_param thing (eid + ':' + eid) for #471746
    var nodeid = ['rel', peid, rtype, eid + ':' + eid].join('-');
    var node = cw.jqNode(nodeid);
    if (!node.attr('cubicweb:type')) {
        node.attr('cubicweb:type', node.val());
        node.val('');
        var divid = ['div', peid, rtype, eid].join('-');
        cw.jqNode(divid).fadeTo('fast', 0.5);
        var noticeid = ['notice', peid, rtype, eid].join('-');
        cw.jqNode(noticeid).fadeIn('fast');
    }
}

function restoreInlinedEntity(peid, rtype, eid) {
    // XXX work around the eid_param thing (eid + ':' + eid) for #471746
    var nodeid = ['rel', peid, rtype, eid + ':' + eid].join('-');
    var node = cw.jqNode(nodeid);
    if (node.attr('cubicweb:type')) {
        node.val(node.attr('cubicweb:type'));
        node.attr('cubicweb:type', '');
        cw.jqNode(['fs', peid, rtype, eid].join('-')).append(node);
        var divid = ['div', peid, rtype, eid].join('-');
        cw.jqNode(divid).fadeTo('fast', 1);
        var noticeid = ['notice', peid, rtype, eid].join('-');
        cw.jqNode(noticeid).hide();
    }
}

function _clearPreviousErrors(formid) {
    // on some case (eg max request size exceeded, we don't know the formid
    if (formid) {
        jQuery('#' + formid + 'ErrorMessage').remove();
        jQuery('#' + formid + ' span.errorMsg').remove();
        jQuery('#' + formid + ' .error').removeClass('error');
    } else {
        jQuery('span.errorMsg').remove();
        jQuery('.error').removeClass('error');
    }
}

function _displayValidationerrors(formid, eid, errors) {
    var globalerrors = [];
    var firsterrfield = null;
    for (fieldname in errors) {
        var errmsg = errors[fieldname];
        if (!fieldname) {
            globalerrors.push(errmsg);
        } else {
            var fieldid = fieldname + ':' + eid;
            var suffixes = ['', '-subject', '-object'];
            var found = false;
            // XXX remove suffixes at some point
            for (var i = 0, length = suffixes.length; i < length; i++) {
                var field = cw.jqNode(fieldname + suffixes[i] + ':' + eid);
                if (field && jQuery(field).attr('type') != 'hidden') {
                    if (!firsterrfield) {
                        firsterrfield = 'err-' + fieldid;
                    }
                    jQuery(field).addClass('error');
                    var span = SPAN({
                        'id': 'err-' + fieldid,
                        'class': "errorMsg"
                    },
                    errmsg);
                    field.before(span);
                    found = true;
                    break;
                }
            }
            if (!found) {
                firsterrfield = formid;
                globalerrors.push(_(fieldname) + ' : ' + errmsg);
            }
        }
    }
    if (globalerrors.length) {
       if (globalerrors.length == 1) {
           var innernode = SPAN(null, globalerrors[0]);
       } else {
           var linodes =[];
           for(var i=0; i<globalerrors.length; i++){
             linodes.push(LI(null, globalerrors[i]));
           }
           var innernode = UL(null, linodes);
       }
        // insert DIV and innernode before the form
        var div = DIV({
            'class': "errorMessage",
            'id': formid + 'ErrorMessage'
        });
        div.appendChild(innernode);
        jQuery('#' + formid).before(div);
    }
    return firsterrfield || formid;
}

function handleFormValidationResponse(formid, onsuccess, onfailure, result, cbargs) {
    // Success
    if (result[0]) {
        if (onsuccess) {
            onsuccess(result, formid, cbargs);
        } else {
            document.location.href = result[1];
        }
        return true;
    }
    if (onfailure && ! onfailure(result, formid, cbargs)) {
        return false;
    }
    unfreezeFormButtons(formid);
    // Failures
    _clearPreviousErrors(formid);
    var descr = result[1];
    var errmsg;
    // Unknown structure
    if ( !cw.utils.isArrayLike(descr) || descr.length != 2 ) {
        errmsg = descr;
    } else {
        _displayValidationerrors(formid, descr[0], descr[1]);
        errmsg = _("please correct errors below");
    }
    updateMessage(errmsg);
    // ensure the browser does not scroll down
    document.location.hash = '#header';
    return false;
}

/**
 * .. function:: unfreezeFormButtons(formid)
 *
 * unfreeze form buttons when the validation process is over
 */
function unfreezeFormButtons(formid) {
    jQuery('#progress').hide();
    // on some case (eg max request size exceeded, we don't know the formid
    if (formid) {
        jQuery('#' + formid + ' .validateButton').removeAttr('disabled');
    } else {
        jQuery('.validateButton').removeAttr('disabled');
    }
    return true;
}

/**
 * .. function:: freezeFormButtons(formid)
 *
 * disable form buttons while the validation is being done
 */
function freezeFormButtons(formid) {
    jQuery('#progress').show();
    jQuery('#' + formid + ' .validateButton').attr('disabled', 'disabled');
    return true;
}

/**
 * .. function:: postForm(bname, bvalue, formid)
 *
 * used by additional submit buttons to remember which button was clicked
 */
function postForm(bname, bvalue, formid) {
    var form = cw.getNode(formid);
    if (bname) {
        var child = form.appendChild(INPUT({
            type: 'hidden',
            name: bname,
            value: bvalue
        }));
    }
    var onsubmit = form.onsubmit;
    if (!onsubmit || (onsubmit && onsubmit())) {
        form.submit();
    }
    if (bname) {
        jQuery(child).remove();
    }
}

/**
 * .. function:: setFormsTarget(node)
 *
 * called on load to set target and iframeso object.
 *
 * .. note::
 *
 *    This was a hack to make form loop handling XHTML compliant.
 *    Since we do not care about xhtml any longer, this may go away.
 *
 * .. note::
 *
 *   `object` nodes might be a potential replacement for iframes
 *
 * .. note::
 *
 *    The form's `target` attribute should probably become a simple data-target
 *    immediately generated server-side.
 *    Since we don't do xhtml any longer, the iframe should probably be either
 *    reconsidered or at least emitted server-side.
 */
function setFormsTarget(node) {
    var $node = jQuery(node || document.body);
    $node.find('form').each(function() {
        var form = jQuery(this);
        var target = form.attr('cubicweb:target');
        if (target) {
            form.attr('target', target);
            /* do not use display: none because some browsers ignore iframe
             * with no display */
            form.append(IFRAME({
                name: target,
                id: target,
                src: 'javascript: void(0)',
                width: '0px',
                height: '0px'
            }));
            form.removeAttr('cubicweb:target'); // useles from now on, pop it
                                                // to make IE9 happy
        }
    });
}

jQuery(document).ready(function() {
    setFormsTarget();
});

/**
 * .. function:: validateForm(formid, action, onsuccess, onfailure)
 *
 * called on traditionnal form submission : the idea is to try
 * to post the form. If the post is successful, `validateForm` redirects
 * to the appropriate URL. Otherwise, the validation errors are displayed
 * around the corresponding input fields.
 */
function validateForm(formid, action, onsuccess, onfailure) {
    freezeFormButtons(formid);
    try {
        var zipped = cw.utils.formContents(formid);
        var args = ajaxFuncArgs('validate_form', null, action, zipped[0], zipped[1]);
        var d = loadRemote(AJAX_BASE_URL, args, 'POST');
    } catch(ex) {
        cw.log('got exception', ex);
        return false;
    }
    d.addCallback(function(result, req) {
        handleFormValidationResponse(formid, onsuccess, onfailure, result);
    });
    return false;
}
