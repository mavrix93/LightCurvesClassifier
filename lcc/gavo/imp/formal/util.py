import re
from zope.interface import implements
from nevow import inevow, tags
from gavo.imp.formal import iformal


_IDENTIFIER_REGEX = re.compile('^[a-zA-Z_][a-zA-Z0-9_]*$')


def titleFromName(name):

    def _():

        it = iter(name)
        last = None

        while 1:
            ch = it.next()
            if ch == '_':
                if last != '_':
                    yield ' '
            elif last in (None,'_'):
                yield ch.upper()
            elif ch.isupper() and not last.isupper():
                yield ' '
                yield ch.upper()
            else:
                yield ch
            last = ch

    return ''.join(_())

def keytocssid(fieldKey, *extras):
    return render_cssid(fieldKey, *extras)

def render_cssid(fieldKey, *extras):
    """
    Render the CSS id for the form field's key.
    """
    l = [tags.slot('formName'), '-', '-'.join(fieldKey.split('.'))]
    for extra in extras:
        l.append('-')
        l.append(extra)
    return l



def validIdentifier(name):
    """
    Test that name is a valid Python identifier.
    """
    return _IDENTIFIER_REGEX.match(name) is not None

class SequenceKeyLabelAdapter(object):
    implements( iformal.IKey, iformal.ILabel )

    def __init__(self, original):
        self.original = original

    def key(self):
        return self.original[0]

    def label(self):
        return self.original[1]


class LazyResource(object):
    implements(inevow.IResource)

    def __init__(self, factory):
        self.factory = factory
        self._resource = None

    def locateChild(self, ctx, segments):
        return self.resource().locateChild(ctx, segments)

    def renderHTTP(self, ctx):
        return self.resource().renderHTTP(ctx)

    def resource(self):
        if self._resource is None:
            self._resource = self.factory()
        return self._resource
