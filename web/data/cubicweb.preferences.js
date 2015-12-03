/**
 * toggle visibility of an element by its id & set current visibility status in a cookie
 *
 */

var prefsValues = {};

function togglePrefVisibility(elemId) {
    clearPreviousMessages();
    jQuery('#' + elemId).toggleClass('hidden');
}

function closeFieldset(fieldsetid) {
    var linklabel = _("open all");
    var linkhref = 'javascript:openFieldset("' + fieldsetid + '")';
    _toggleFieldset(fieldsetid, 1, linklabel, linkhref);
}

function openFieldset(fieldsetid) {
    var linklabel = _("close all");
    var linkhref = 'javascript:closeFieldset("' + fieldsetid + '")';
    _toggleFieldset(fieldsetid, 0, linklabel, linkhref);
}

function _toggleFieldset(fieldsetid, closeaction, linklabel, linkhref) {
    jQuery('#' + fieldsetid).find('div.openlink').each(function() {
        var link = A({
            'href': "javascript:$.noop();",
            'onclick': linkhref
        },
        linklabel);
        jQuery(this).empty().append(link);
    });
    jQuery('#' + fieldsetid).find('fieldset[id]').each(function() {
        var fieldset = jQuery(this);
        if (closeaction) {
            fieldset.addClass('hidden');
        } else {
            fieldset.removeClass('hidden');
            linkLabel = (_("open all"));
        }
    });
}

function validatePrefsForm(formid) {
    clearPreviousMessages();
    _clearPreviousErrors(formid);
    return validateForm(formid, null, submitSuccess, submitFailure);
}

function submitFailure(result, formid, cbargs) {
    var $form = jQuery('#' + formid);
    var dom = DIV({'class': 'critical'}, _("please correct errors below"));
    $form.find('div.formsg').empty().append(dom);
    unfreezeFormButtons(formid);
    var descr = result[1];
    _displayValidationerrors(formid, descr[0], descr[1]);
    $form.find('span.error').next().focus();
    return false; // so handleFormValidationResponse doesn't try to display error
}

function submitSuccess(result, formid, cbargs) {
    var $form = jQuery('#' + formid);
    setCurrentValues($form);
    var dom = DIV({'class': 'msg'}, _("changes applied"));
    $form.find('div.formsg').empty().append(dom);
    $form.find('input').removeClass('changed');
    checkValues($form, true);
    return;
}

function clearPreviousMessages() {
    jQuery('div#appMsg').addClass('hidden');
    jQuery('div.formsg').empty();
}

function checkValues(form, success) {
    var unfreezeButtons = false;
    jQuery(form).find('select').each(function() {
        unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
    });
    jQuery(form).find('[type=text]').each(function() {
        unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
    });
    jQuery(form).find('input[type=radio]:checked').each(function() {
        unfreezeButtons = _checkValue(jQuery(this), unfreezeButtons);
    });

    if (unfreezeButtons) {
        unfreezeFormButtons(form.attr('id'));
    } else {
        if (!success) {
            clearPreviousMessages();
        }
        _clearPreviousErrors(form.attr('id'));
        freezeFormButtons(form.attr('id'));
    }
}

function _checkValue(input, unfreezeButtons) {
    var currentValue = prefsValues[input.attr('name')];
    if (currentValue != input.val()) {
        input.addClass('changed');
        unfreezeButtons = true;
    } else {
        input.removeClass('changed');
        jQuery('span[id="err-' + input.attr('id') + '"]').remove();
    }
    input.removeClass('error');
    return unfreezeButtons;
}

function setCurrentValues(form) {
    jQuery(form).find('[name^=value]').each(function() {
        var input = jQuery(this);
        var name = input.attr('name');
        if (input.attr('type') == 'radio') {
            // NOTE: there seems to be a bug with jQuery(input).attr('checked')
            //       in our case, we can't rely on its value, we use
            //       the DOM API instead.
            if (input[0].checked) {
                prefsValues[name] = input.val();
            }
        } else {
            prefsValues[name] = input.val();
        }
        jQuery(form).find('input[name="edits-' + name + '"]').val(prefsValues[name]);
    });
}

function initEvents() {
    jQuery('form').each(function() {
        var form = jQuery(this);
        //freezeFormButtons(form.attr('id'));
        form.find('.validateButton').attr('disabled', 'disabled');
        form.find('input[type=text]').keyup(function() {
            checkValues(form);
        });
        form.find('input[type=radio]').change(function() {
            checkValues(form);
        });
        form.find('select').change(function() {
            checkValues(form);
        });
        setCurrentValues(form);
    });
}

$(document).ready(function() {
    initEvents();
});

