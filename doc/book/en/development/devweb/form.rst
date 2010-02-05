Form construction
------------------
CubicWeb provides usual form/field/widget/renderer abstraction to provde
some generic building blocks which will greatly help you in building forms
properly integrated with |cubicweb| (coherent display, error handling, etc...)

A form basically only hold a set of fields, and is bound to a renderer that is
responsible to layout them. Each field is bound to a widget that will be used
to fill in value(s) for that field.

The Field class and basic fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: cubicweb.web.formfields.Field


Existing field types are:

.. autoclass:: cubicweb.web.formfields.StringField
.. autoclass:: cubicweb.web.formfields.PasswordField
.. autoclass:: cubicweb.web.formfields.RichTextField
.. autoclass:: cubicweb.web.formfields.FileField
.. autoclass:: cubicweb.web.formfields.EditableFileField
.. autoclass:: cubicweb.web.formfields.IntField
.. autoclass:: cubicweb.web.formfields.BooleanField
.. autoclass:: cubicweb.web.formfields.FloatField
.. autoclass:: cubicweb.web.formfields.DateField
.. autoclass:: cubicweb.web.formfields.DateTimeField
.. autoclass:: cubicweb.web.formfields.TimeField
.. autoclass:: cubicweb.web.formfields.RelationField
.. XXX still necessary?
.. autoclass:: cubicweb.web.formfields.CompoundField


Widgets
~~~~~~~
Base class for widget is :class:cubicweb.web.formwidgets.FieldWidget class.

Existing widget types are:

.. autoclass:: cubicweb.web.formwidgets.HiddenInput
.. autoclass:: cubicweb.web.formwidgets.TextInput
.. autoclass:: cubicweb.web.formwidgets.PasswordInput
.. autoclass:: cubicweb.web.formwidgets.PasswordSingleInput
.. autoclass:: cubicweb.web.formwidgets.FileInput
.. autoclass:: cubicweb.web.formwidgets.ButtonInput
.. autoclass:: cubicweb.web.formwidgets.TextArea
.. autoclass:: cubicweb.web.formwidgets.FCKEditor
.. autoclass:: cubicweb.web.formwidgets.Select
.. autoclass:: cubicweb.web.formwidgets.CheckBox
.. autoclass:: cubicweb.web.formwidgets.Radio
.. autoclass:: cubicweb.web.formwidgets.DateTimePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryDateTimePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryDatePicker
.. autoclass:: cubicweb.web.formwidgets.JQueryTimePicker
.. autoclass:: cubicweb.web.formwidgets.AjaxWidget
.. autoclass:: cubicweb.web.formwidgets.AutoCompletionWidget
.. autoclass:: cubicweb.web.formwidgets.EditableURLWidget

.. XXX StaticFileAutoCompletionWidget, RestrictedAutoCompletionWidget, AddComboBoxWidget, IntervalWidget, HorizontalLayoutWidget

The following classes, which are not proper widget (they are not associated to
field) but are used as form controls, may also be useful: Button, SubmitButton,
ResetButton, ImgButton,


Of course you can not use any widget with any field...

Renderers
~~~~~~~~~
XXX feed me
