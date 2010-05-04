
Dissection of a Form
--------------------

This is done (again) with a vanilla instance of the `tracker`_
cube. We will populate the database with a bunch of entities and see
what kind of job the automatic entity form does.

.. _`tracker`: http://www.cubicweb.org/project/cubicweb-tracker

Patching the session object
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to play interactively with web side application objects, we
have to cheat a bit: we will decorate the session object with some
missing artifacts that should belong to a web request object. With
that we can instantiate and render forms interactively.

The function below does the minimum to allow going through this
exercice. Some attributes or methods may be missing for other
purposes. It is nevertheless not complicated to enhance it if need
arises.

.. sourcecode:: python

 def monkey_patch_session(session):
     """ useful to use the cw shell session object
     with web appobjects, which expect more than a plain
     data repository session
     """
     # for autoform selection
     session.json_request = False
     session.url = lambda: u'http://perdu.com'
     session.session = session
     session.form = {}
     session.list_form_param = lambda *args: []
     # for render
     session.use_fckeditor = lambda: False
     session._ressources = []
     session.add_js = session.add_css = lambda *args: session._ressources.append(args)
     session.external_resource = lambda x:{}
     session._tabcount = 0
     def next_tabindex():
         session._tabcount += 1
         return session._tabcount
     session.next_tabindex = next_tabindex
     return session

Populating the database
~~~~~~~~~~~~~~~~~~~~~~~

We should start by setting up a bit of context: a project with two
unpublished versions, and a ticket linked to the project and the first
version.

.. sourcecode:: python

 >>> p = rql('INSERT Project P: P name "cubicweb"')
 >>> for num in ('0.1.0', '0.2.0'):
 ...  rql('INSERT Version V: V num "%s", V version_of P WHERE P eid %%(p)s' % num, {'p': p[0][0]})
 ...
 <resultset 'INSERT Version V: V num "0.1.0", V version_of P WHERE P eid %(p)s' (1 rows): [765L] (('Version',))>
 <resultset 'INSERT Version V: V num "0.2.0", V version_of P WHERE P eid %(p)s' (1 rows): [766L] (('Version',))>
 >>> t = rql('INSERT Ticket T: T title "let us write more doc", T done_in V, '
             'T concerns P WHERE V num "0.1.0"', P eid %(p)s', {'p': p[0][0]})
 >>> commit()

Now let's see what the edition form builds for us.

.. sourcecode:: python

 >>> monkey_patch_session(session)
 >>> form = session.vreg['forms'].select('edition', session, rset=rql('Ticket T'))
 >>> html = form.render()

This creates an automatic entity form. The ``.render()`` call yields
an html (unicode) string. The html output is shown below (with
internal fieldset omitted).

Looking at the html output
~~~~~~~~~~~~~~~~~~~~~~~~~~

The form enveloppe
''''''''''''''''''

.. sourcecode:: html

 <div class="iformTitle"><span>main informations</span></div>
 <div class="formBody">
  <form action="http://crater:9999/validateform" method="post" enctype="application/x-www-form-urlencoded"
        id="entityForm" onsubmit="return freezeFormButtons(&#39;entityForm&#39;);"
        class="entityForm" cubicweb:target="eformframe">
    <div id="progress">validating...</div>
    <fieldset>
      <input name="__form_id" type="hidden" value="edition" />
      <input name="__errorurl" type="hidden" value="http://perdu.com#entityForm" />
      <input name="__domid" type="hidden" value="entityForm" />
      <input name="__type:763" type="hidden" value="Ticket" />
      <input name="eid" type="hidden" value="763" />
      <input name="__maineid" type="hidden" value="763" />
      <input name="_cw_edited_fields:763" type="hidden"
             value="concerns-subject,done_in-subject,priority-subject,type-subject,title-subject,description-subject,__type,_cw_generic_field" />
      ...
    </fieldset>
   </form>
 </div>

The main fieldset encloses a set of hidden fields containing various
metadata, that will be used by the `edit controller` to process it
back correctly.

The `freezeFormButtons(...)` javascript callback defined on the
``conlick`` event of the form element prevents accidental multiple
clicks in a row.

The ``action`` of the form is mapped to the `validateform` controller
(situated in :mod:`cubicweb.web.views.basecontrollers`).

The attributes section
''''''''''''''''''''''

We can have a look at some of the inner nodes of the form. Some fields
are omitted as they are redundant for our purposes.

.. sourcecode:: html

      <fieldset class="default">
        <table class="attributeForm">
          <tr class="title_subject_row">
            <th class="labelCol"><label class="required" for="title-subject:763">title</label></th>
            <td>
              <input id="title-subject:763" maxlength="128" name="title-subject:763" size="45"
                     tabindex="1" type="text" value="let us write more doc" />
            </td>
          </tr>
          ... (description field omitted) ...
          <tr class="priority_subject_row">
            <th class="labelCol"><label class="required" for="priority-subject:763">priority</label></th>
            <td>
              <select id="priority-subject:763" name="priority-subject:763" size="1" tabindex="4">
                <option value="important">important</option>
                <option selected="selected" value="normal">normal</option>
                <option value="minor">minor</option>
              </select>
              <div class="helper">importance</div>
            </td>
          </tr>
          ... (type field omitted) ...
          <tr class="concerns_subject_row">
            <th class="labelCol"><label class="required" for="concerns-subject:763">concerns</label></th>
            <td>
              <select id="concerns-subject:763" name="concerns-subject:763" size="1" tabindex="6">
                <option selected="selected" value="760">Foo</option>
              </select>
            </td>
          </tr>
          <tr class="done_in_subject_row">
            <th class="labelCol"><label for="done_in-subject:763">done in</label></th>
            <td>
              <select id="done_in-subject:763" name="done_in-subject:763" size="1" tabindex="7">
                <option value="__cubicweb_internal_field__"></option>
                <option selected="selected" value="761">Foo 0.1.0</option>
                <option value="762">Foo 0.2.0</option>
              </select>
              <div class="helper">version in which this ticket will be / has been  done</div>
            </td>
          </tr>
        </table>
      </fieldset>


Note that the whole form layout has been computed by the form
renderer. It is the renderer which produces the table
structure. Otherwise, the fields html structure is emitted by their
associated widget.

While it is called the `attributes` section of the form, it actually
contains attributes and *mandatory relations*. For each field, we
observe:

* a dedicated row with a specific class, such as ``title_subject_row``
  (responsability of the form renderer)

* an html widget (input, select, ...) with:

  * an id built from the ``rtype-role:eid`` pattern

  * a name built from the same pattern

  * possible values or preselected options

The relations section
'''''''''''''''''''''

.. sourcecode:: html

      <fieldset class="This ticket :">
        <legend>This ticket :</legend>
        <table class="attributeForm">
          <tr class="_cw_generic_field_None_row">
            <td colspan="2">
              <table id="relatedEntities">
                <tr><th>&#160;</th><td>&#160;</td></tr>
                <tr id="relationSelectorRow_763" class="separator">
                  <th class="labelCol">
                    <select id="relationSelector_763" tabindex="8"
                            onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,763);">
                      <option value="">select a relation</option>
                      <option value="appeared_in_subject">appeared in</option>
                      <option value="custom_workflow_subject">custom workflow</option>
                      <option value="depends_on_object">dependency of</option>
                      <option value="depends_on_subject">depends on</option>
                      <option value="identical_to_subject">identical to</option>
                      <option value="see_also_subject">see also</option>
                    </select>
                  </th>
                  <td id="unrelatedDivs_763"></td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </fieldset>

The optional relations are grouped into a drop-down combo
box. Selection of an item triggers a javascript function which will:

* show already related entities in the div of id `relatedentities`
  using a two-colown layout, with an action to allow deletion of
  individual relations (there are none in this example)

* provide a relation selector in the div of id `relationSelector_EID`
  to allow the user to set up relations and trigger dynamic action on
  the last div

* fill the div of id `unrelatedDivs_EID` with a dynamically computed
  selection widget allowing direct selection of an unrelated (but
  relatable) entity or a switch towards the `search mode` of
  |cubicweb| which allows full browsing and selection of an entity
  using a dedicated action situated in the left column boxes.


The buttons zone
''''''''''''''''

Finally comes the buttons zone.

.. sourcecode:: html

      <table width="100%">
        <tbody>
          <tr>
            <td align="center">
              <button class="validateButton" tabindex="9" type="submit" value="validate">
                <img alt="OK_ICON" src="{}" />validate
              </button>
            </td>
            <td style="align: right; width: 50%;">
              <button class="validateButton"
                      onclick="postForm(&#39;__action_apply&#39;, &#39;button_apply&#39;, &#39;entityForm&#39;)"
                      tabindex="10" type="button" value="apply">
                <img alt="APPLY_ICON" src="{}" />apply
              </button>
              <button class="validateButton"
                      onclick="postForm(&#39;__action_cancel&#39;, &#39;button_cancel&#39;, &#39;entityForm&#39;)"
                      tabindex="11" type="button" value="cancel">
                <img alt="CANCEL_ICON" src="{}" />cancel
              </button>
            </td>
          </tr>
        </tbody>
      </table>

The most notable artifacts here are the ``postForm(...)`` calls
defined on click events on these buttons. This function basically
submits the form. XXX validateform vs validateForm, ajax or not ?
