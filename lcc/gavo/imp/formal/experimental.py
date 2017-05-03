from nevow import appserver, rend
from gavo.imp.formal.form import FormsResourceBehaviour


class FormPage(rend.Page):
    """
    Base class for pages that contain a Form.

    XXX This really, really needs to turn into a ComponentPage that iterates
    a bunch of component behaviours looking for something that succeeded.

    The components probably needs to be per-interface, i.e IResource for
    locateChild/renderHTTP, IRenderer for render_, etc.
    """

    def __init__(self, *a, **k):
        rend.Page.__init__(self, *a, **k)
        self._formsComponent = FormsResourceBehaviour(parent=self)

    def locateChild(self, ctx, segments):
        def gotResult(result):
            if result is not appserver.NotFound:
                return result
            return rend.Page.locateChild(self, ctx, segments)
        d = defer.maybeDeferred(self._formsComponent.locateChild, ctx, segments)
        d.addCallback(gotResult)
        return d

    def renderHTTP(self, ctx):
        def gotResult(result):
            if result is not None:
                return result
            return rend.Page.renderHTTP(self, ctx)
        d = defer.maybeDeferred(self._formsComponent.renderHTTP, ctx)
        d.addCallback(gotResult)
        return d

    def render_form(self, name):
        return self._formsComponent.render_form(name)

    def formFactory(self, ctx, name):
        # Find the factory method
        factory = getattr(self, 'form_%s'%name, None)
        if factory is not None:
            return factory(ctx)
        # Try the super class
        s = super(FormPage, self)
        if hasattr(s,'formFactory'):
            return s.formFactory(ctx, name)

