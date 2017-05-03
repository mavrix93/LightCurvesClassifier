"""
Form implementation and high-level renderers.
"""

from zope.interface import Interface
from twisted.internet import defer
from twisted.python.components import registerAdapter
from nevow import appserver, context, loaders, inevow, rend, tags as T, url
from nevow.util import getPOSTCharset
from zope.interface import implements

from gavo.imp.formal import iformal, util, validation
from gavo.imp.formal.resourcemanager import ResourceManager


SEPARATOR = '!!'
FORMS_KEY = '__nevow_form__'
WIDGET_RESOURCE_KEY = 'widget_resource'



# Backwards compatability/workaround until there's nothing left in Formal or
# application code that adapts the context to IFormErrors.
def formErrorsFinder(ctx):
    form = iformal.IForm(ctx)
    return form.errors

registerAdapter(formErrorsFinder, context.WovenContext, iformal.IFormErrors)



def renderForm(name):

    def _(ctx, data):

        def _processForm( form, ctx, name ):
            # Remember the form
            ctx.remember(form, iformal.IForm)

            # Create a keyed tag that will render the form when flattened.
            tag = T.invisible(key=name)[inevow.IRenderer(form)]

            # Create a new context, referencing the above tag, so that we don't
            # pollute the current context with anything the form needs during
            # rendering.
            ctx = context.WovenContext(parent=ctx, tag=tag)

            # Find errors for *this* form and remember things on the context
            if form.errors:
                ctx.remember(form.errors.data, iformal.IFormData)
            else:
                ctx.remember(form.data or {}, iformal.IFormData)

            return ctx
        d = defer.succeed( ctx )
        d.addCallback( locateForm, name )
        d.addCallback( _processForm, ctx, name )
        return d

    return _


class Action(object):
    """Tracks an action that has been added to a form.
    """
    def __init__(self, callback, name, validate, label):

        if not util.validIdentifier(name):
            import warnings
            warnings.warn('[0.9] Invalid action name %r. This will become an error in the future.' %
                    name, FutureWarning, stacklevel=3)

        self.callback = callback
        self.name = name
        self.validate = validate
        if label is None:
            self.label = util.titleFromName(name)
        else:
            self.label = label



def itemKey(item):
    """
    Build the form item's key.  This currently always is the item name.
    """
    return item.name

# The original formal code included ancestor names as below.  We don't
# want this in DaCHS since our parameter names may be important (e.g.
# in VO protocols we're funneling through the formal parsers).
    parts = [item.name]
    parent = item.itemParent
    while parent is not None:
        parts.append(parent.name)
        parent = parent.itemParent
    parts.reverse()
    return '.'.join(parts)



class Field(object):


    itemParent = None


    def __init__(self, name, type, widgetFactory=None, label=None,
            description=None, cssClass=None, default=None):
        if not util.validIdentifier(name):
            raise ValueError('%r is an invalid field name'%name)
        if label is None:
            label = util.titleFromName(name)
        if widgetFactory is None:
            widgetFactory = iformal.IWidget
        self.name = name
        self.type = type
        self.widgetFactory = widgetFactory
        self.label = label
        self.description = description
        self.cssClass = cssClass
        self.default = default


    def setItemParent(self, itemParent):
        self.itemParent = itemParent


    key = property(lambda self: itemKey(self))


    def makeWidget(self):
        return self.widgetFactory(self.type)


    def process(self, ctx, form, args, errors):

        # If the type is immutable then copy the original value to args in case
        # another validation error causes this field to be re-rendered.
        if self.type.immutable:
            args[self.key] = form.data.get(self.key)
            return

        # Process the input using the widget, storing the data back on the form.
        try:
            if self.default is not None:
                form.data[self.key] = self.makeWidget(
                    ).processInput(ctx, self.key, args, self.default)
            else:
                form.data[self.key] = self.makeWidget(
                    ).processInput(ctx, self.key, args)
        except validation.FieldError, e:
            if e.fieldName is None:
                e.fieldName = self.key
            errors.add(e)



class FieldFragment(rend.Fragment):
    implements(inevow.IRenderer)


    docFactory = loaders.stan(
        T.div(id=T.slot('fieldId'), _class=T.slot('class'),
                render=T.directive('field'))[
            T.label(_class='label', _for=T.slot('id'))[T.slot('label')],
            T.div(_class='inputs')[T.slot('inputs')],
            T.slot('description'),
            T.slot('message'),
            ])


    hiddenDocFactory = loaders.stan(
            T.invisible(render=T.directive('field'))[T.slot('inputs')])


    def __init__(self, field):
        self.field = field
        # Nasty hack to work out if this is a hidden field. Keep the widget
        # for later anyway.
        self.widget = field.makeWidget()
        if getattr(self.widget, 'inputType', None) == 'hidden':
            self.docFactory = self.hiddenDocFactory


    def render_field(self, ctx, data):

        # The field we're rendering
        field = self.field

        # Get stuff from the context
        formData = iformal.IFormData(ctx)
        formErrors = iformal.IFormErrors(ctx, None)

        # Find any error
        if formErrors is None:
            error = None
        else:
            error = formErrors.getFieldError(field.key)

        # Build the error message
        if error is None:
            message = ''
        else:
            message = T.div(class_='message')[error.message]

        # Create the widget (it's created in __init__ as a hack)
        widget = self.widget

        # Build the list of CSS classes
        classes = [
            'field',
            field.type.__class__.__name__.lower(),
            widget.__class__.__name__.lower(),
            ]
        if field.type.required:
            classes.append('required')
        if field.cssClass:
            classes.append(field.cssClass)
        if error:
            classes.append('error')

        # Create the widget and decide the method that should be called
        if field.type.immutable:
            render = widget.renderImmutable
        else:
            render = widget.render

        # Fill the slots
        tag = ctx.tag
        tag.fillSlots('id', util.render_cssid(field.key))
        tag.fillSlots('fieldId', [util.render_cssid(field.key), '-field'])
        tag.fillSlots('class', ' '.join(classes))
        tag.fillSlots('label', field.label)
        tag.fillSlots('inputs', render(ctx, field.key, formData,
            formErrors))
        tag.fillSlots('message', message)
        tag.fillSlots('description',
                T.div(class_='description')[field.description or ''])

        return ctx.tag



registerAdapter(FieldFragment, Field, inevow.IRenderer)



class AddHelperMixin(object):
    """
    A mixin that provides methods for common uses of add(...).
    """

    
    def addGroup(self, *a, **k):
        return self.add(Group(*a, **k))
        
        
    def addField(self, *a, **k):
        return self.add(Field(*a, **k))
        
        
    def __getitem__(self, items):
        """
        Overridden to allow stan-style construction of forms.
        """
        # Items may be a list or a scalar so stick a scalar into a list
        # immediately to simplify the code.
        try:
            items = iter(items)
        except TypeError:
            items = [items]
        # Add each item
        for item in items:
            self.add(item)
        # Return myself
        return self


class Group(AddHelperMixin, object):


    itemParent = None


    def __init__(self, name, label=None, description=None, cssClass=None):
        if label is None:
            label = util.titleFromName(name)
        self.name = name
        self.label = label
        self.description = description
        self.cssClass = cssClass
        self.items = FormItems(self)
        # Forward to FormItems methods
        self.add = self.items.add
        self.getItemByName = self.items.getItemByName


    key = property(lambda self: itemKey(self))
    
    
    def setItemParent(self, itemParent):
        self.itemParent = itemParent


    def process(self, ctx, form, args, errors):
        for item in self.items:
            item.process(ctx, form, args, errors)



class GroupFragment(rend.Fragment):


    docFactory = loaders.stan(
            T.fieldset(id=T.slot('id'), class_=T.slot('cssClass'),
                    render=T.directive('group'))[
                T.legend[T.slot('label')],
                T.div(class_='description')[T.slot('description')],
                T.slot('items'),
                ]
            )


    def __init__(self, group):
        super(GroupFragment, self).__init__()
        self.group = group


    def render_group(self, ctx, data):

        # Get a reference to the group, for simpler code.
        group = self.group

        # Build the CSS class string
        cssClass = ['group']
        if group.cssClass is not None:
            cssClass.append(group.cssClass)
        cssClass = ' '.join(cssClass)

        # Fill the slots
        tag = ctx.tag
        tag.fillSlots('id', util.render_cssid(group.key))
        tag.fillSlots('cssClass', cssClass)
        tag.fillSlots('label', group.label)
        tag.fillSlots('description', group.description or '')
        tag.fillSlots('items', [inevow.IRenderer(item) for item in
                group.items])
        return ctx.tag



registerAdapter(GroupFragment, Group, inevow.IRenderer)



class Form(AddHelperMixin, object):

    implements( iformal.IForm )

    callback = None
    actions = None

    def __init__(self, callback=None):
        if callback is not None:
            self.callback = callback
        self.resourceManager = ResourceManager()
        self.data = {}
        self.items = FormItems(None)
        self.errors = FormErrors()
        # Forward to FormItems methods
        self.add = self.items.add
        self.getItemByName = self.items.getItemByName
        self.actionMaterial = None


    def addAction(self, callback, name="submit", validate=True, label=None):
        if self.actions is None:
            self.actions = []
        if name in [action.name for action in self.actions]:
            raise ValueError('Action with name %r already exists.' % name)
        self.actions.append( Action(callback, name, validate, label) )

    def process(self, ctx):

        request = inevow.IRequest(ctx)
        charset = getPOSTCharset(ctx)

        # Get the request args and decode the arg names
        args = dict([(k.decode(charset),v) for k,v in request.args.items()])

        # Find the callback to use, defaulting to the form default
        callback, validate = self.callback, True
        if self.actions is not None:
            for action in self.actions:
                if action.name in args:
                    # Remove it from the data
                    args.pop(action.name)
                    # Remember the callback and whether to validate
                    callback, validate = action.callback, action.validate
                    break

        # IE does not send a button name in the POST args for forms containing
        # a single field when the user presses <enter> to submit the form. If
        # we only have one possible action then we can safely assume that's the
        # action to take.
        #
        # If there are 0 or 2+ actions then we can't assume anything because we
        # have no idea what order the buttons are on the page (someone might
        # have altered the DOM using JavaScript for instance). In that case
        # throw an error and make it a problem for the developer.
        if callback is None:
            if self.actions is None or len(self.actions) != 1:
                raise Exception('The form has no callback and no action was found.')
            else:
                callback, validate = self.actions[0].callback, \
                        self.actions[0].validate

        # Remember the args in case validation fails.
        self.errors.data = args

        # Iterate the items and collect the form data and/or errors.
        for item in self.items:
            item.process(ctx, self, args, self.errors)

        if self.errors and validate:
            return self.errors

        def _clearUpResources( r ):
            if not self.errors:
                self.resourceManager.clearUpResources()
            return r

        d = defer.maybeDeferred(callback, ctx, self, self.data)
        d.addCallback( _clearUpResources )
        d.addErrback(self._cbFormProcessingFailed, ctx)
        return d

    def _cbFormProcessingFailed(self, failure, ctx):
        e = failure.value
        failure.trap(validation.FormError, validation.FieldError)
        self.errors.add(failure.value)
        return self.errors



class FormItems(object):
    """
    A managed collection of form items.
    """


    def __init__(self, itemParent):
        self.items = []
        self.itemParent = itemParent


    def __iter__(self):
        return iter(self.items)


    def add(self, item):
        # Check the item name is unique
        if item.name in [i.name for i in self.items]:
            raise ValueError('Item named %r already added to %r' %
                    (item.name, self))
        # Add to child items and set self the parent
        self.items.append(item)
        item.setItemParent(self.itemParent)
        return item


    def getItemByName(self, name):
        # since we have flat names in the DC, we need to look 
        # into each subordinate container.  Original formal could
        # use the code below
        for item in self.items:
            if item.name==name:
                return item
            try:
                return item.getItemByName(name)
            except (AttributeError, KeyError):
                # child either is no container or doesn't have the item
                pass
        raise KeyError("No item called %r" % name)
        '''
        name = name.split('.', 1)
        if len(name) == 1:
            name, rest = name[0], None
        else:
            name, rest = name[0], name[1]
        for item in self.items:
            if item.name == name:
                if rest is None:
                    return item
                return item.getItemByName(rest)
        raise KeyError("No item called %r" % name)
        '''



class FormErrors(object):
    implements( iformal.IFormErrors )

    def __init__(self):
        self.errors = []

    def __iter__(self):
      return iter(self.errors)

    def add(self, error):
        self.errors.append(error)

    def getFieldError(self, name):
        fieldErrors = [e for e in self.errors if isinstance(e, validation.FieldError)]
        for error in fieldErrors:
            if error.fieldName == name:
                return error

    def getFormErrors(self):
        return self.errors

    def __nonzero__(self):
        return len(self.errors) != 0


class FormResource(object):
    implements(inevow.IResource)

    def locateChild(self, ctx, segments):
        # The form name is the first segment
        formName = segments[0]
        if segments[1] == WIDGET_RESOURCE_KEY:
            # Serve up file from the resource manager
            d = locateForm(ctx, formName)
            d.addCallback(self._fileFromWidget, ctx, segments[2:])
            return d
        return appserver.NotFound

    def renderHTTP(self, ctx):
        raise NotImplemented()

    def _fileFromWidget(self, form, ctx, segments):
        ctx.remember(form, iformal.IForm)
        widget = form.getItemByName(segments[0]).makeWidget()
        return widget.getResource(ctx, segments[0], segments[1:])


class FormsResourceBehaviour(object):
    """
    I provide the IResource behaviour needed to process and render a page
    containing a Form.
    """

    def __init__(self, **k):
        parent = k.pop('parent')
        super(FormsResourceBehaviour, self).__init__(**k)
        self.parent = parent

    def locateChild(self, ctx, segments):
        if segments[0] == FORMS_KEY:
            self.remember(ctx)
            return FormResource(), segments[1:]
        return appserver.NotFound

    def renderHTTP(self, ctx):
        # Get hold of the request
        request = inevow.IRequest(ctx)
        # Try to find the form name
        formName = request.args.get(FORMS_KEY, [None])[0]
        if formName is None:
            return None
				# delete forms key to prevent infinite recursion.
        del request.args[FORMS_KEY]
        # Find the actual form and process it
        self.remember(ctx)
        d = defer.succeed(ctx)
        d.addCallback(locateForm, formName)
        d.addCallback(self._processForm, ctx)
        return d

    def remember(self, ctx):
        ctx.remember(self.parent, iformal.IFormFactory)

    def render_form(self, name):
        def _(ctx, data):
            self.remember(ctx)
            return renderForm(name)
        return _

    def _processForm(self, form, ctx):
        ctx.remember(form, iformal.IForm)
        d = defer.maybeDeferred(form.process, ctx)
        d.addCallback(self._formProcessed, ctx)
        return d

    def _formProcessed(self, result, ctx):
        if isinstance(result, FormErrors):
            return None
        elif result is None:
            resource = url.URL.fromContext(ctx)
        else:
            resource = result
        return resource


class ResourceMixin(object):
    implements( iformal.IFormFactory )
    
    __formsBehaviour = None
    
    def __behaviour(self):
        if self.__formsBehaviour is None:
            self.__formsBehaviour = FormsResourceBehaviour(parent=self)
        return self.__formsBehaviour
    
    def locateChild(self, ctx, segments):
        def gotResult(result):
            if result is not appserver.NotFound:
                return result
            return super(ResourceMixin, self).locateChild(ctx, segments)
        self.remember(self, iformal.IFormFactory)
        d = defer.maybeDeferred(self.__behaviour().locateChild, ctx, segments)
        d.addCallback(gotResult)
        return d

    def renderHTTP(self, ctx):
        def gotResult(result):
            if result is not None:
                return result
            return super(ResourceMixin, self).renderHTTP(ctx)
        self.remember(self, iformal.IFormFactory)
        d = defer.maybeDeferred(self.__behaviour().renderHTTP, ctx)
        d.addCallback(gotResult)
        return d

    def crash(self, failure):
      failure.printTraceback()
      raise failure.value

    def render_form(self, name):
        return self.__behaviour().render_form(name)

    def formFactory(self, ctx, name):
        factory = getattr(self, 'form_%s'%name, None)
        if factory is not None:
            return factory(ctx)
        s = super(ResourceMixin, self)
        if hasattr(s,'formFactory'):
            return s.formFactory(ctx, name)



class IKnownForms(Interface):
    """Marker interface used to locate a dict instance containing the named
    forms we know about during this request.
    """


class KnownForms(dict):
    implements( IKnownForms )


def locateForm(ctx, name):
    """Locate a form by name.

    Initially, a form is located by calling on an IFormFactory that is found
    on the context. Once a form has been found, it is remembered in an
    KnownForms instance for the lifetime of the request.

    This ensures that the form that is located during form processing will be
    the same instance that is located when a form is rendered after validation
    failure.
    """
    # Get hold of the request
    request = inevow.IRequest(ctx)
    # Find or create the known forms instance
    knownForms = request.getComponent(IKnownForms)
    if knownForms is None:
        knownForms = KnownForms()
        request.setComponent(IKnownForms, knownForms)
    # See if the form is already known
    form = knownForms.get(name)
    if form is not None:
        return form
    # Not known yet, ask a form factory to create the form
    factory = ctx.locate(iformal.IFormFactory)

    def cacheForm( form, name ):
        if form is None:
            raise Exception('Form %r not found'%name)
        form.name = name
        # Make it a known
        knownForms[name] = form
        return form

    d = defer.succeed( None )
    d.addCallback( lambda r : factory.formFactory( ctx, name ) )
    d.addCallback( cacheForm, name )
    return d

def widgetResourceURL(name):
    return url.here.child(FORMS_KEY).child(name).child(WIDGET_RESOURCE_KEY)

def widgetResourceURLFromContext(ctx,name):
    # Could this replace widgetResourceURL?
    u = url.URL.fromContext(ctx)
    if u.pathList()[-1] != FORMS_KEY:
        u = u.child(FORMS_KEY)
    return u.child(name).child(WIDGET_RESOURCE_KEY)

class FormRenderer(object):
    implements( inevow.IRenderer )

    loader = loaders.stan(
            T.form(**{'id': T.slot('formName'), 'action': T.slot('formAction'),
                'class': 'nevow-form', 'method': 'post', 'enctype':
                'multipart/form-data', 'accept-charset': 'utf-8'})[
            T.div[
                T.input(type='hidden', name='_charset_'),
                T.input(type='hidden', name=FORMS_KEY, value=T.slot('formName')),
                T.slot('formErrors'),
                T.slot('formItems'),
                T.div(class_='actions')[
                    T.slot('formActions'),
                    ],
                ],
            ]
        )

    def __init__(self, original, *a, **k):
        super(FormRenderer, self).__init__(*a, **k)
        self.original = original

    def rend(self, ctx, data):
        tag = T.invisible[self.loader.load()]
        tag.fillSlots('formName', self.original.name)
        tag.fillSlots('formAction', 
            getattr(self.original, "actionURL", None) or url.here)
        tag.fillSlots('formErrors', self._renderErrors)
        tag.fillSlots('formItems', self._renderItems)
        tag.fillSlots('formActions', self._renderActions)
        return tag

    def _renderErrors(self, ctx, data):

        if not self.original.errors:
            return ''

        errors = self.original.errors.getFormErrors()

        errorList = T.ul()
        for error in errors:
            if isinstance(error, validation.FormError):
                errorList[ T.li[ error.message ] ]
        for error in errors:
            if isinstance(error, validation.FieldError):
                item = self.original.getItemByName(error.fieldName)
                errorList[ T.li[ T.strong[ item.label, ' : ' ], error.message ] ]
        return T.div(class_='errors')[ T.p['Please correct the following error(s):'], errorList ]

    def _renderItems(self, ctx, data):
        if self.original.items is None:
            yield ''
            return
        for item in self.original.items:
            yield inevow.IRenderer(item)

    def _renderActions(self, ctx, data):

        if self.original.actions is None:
            yield ''
            return

        for action in self.original.actions:
            yield T.invisible(data=action, render=self._renderAction)
        
        if self.original.actionMaterial:
            yield self.original.actionMaterial


    def _renderAction(self, ctx, data):
        return T.input(type='submit', id='%s-action-%s'%(self.original.name, data.name), name=data.name, value=data.label)


registerAdapter(FormRenderer, Form, inevow.IRenderer)

# vim:sta:et:sw=4:
