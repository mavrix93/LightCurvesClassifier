from zope.interface import implements
from nevow import tags as T
from gavo.imp.formal import iformal
from gavo.imp.formal.util import render_cssid

_UNSET = object()

class MultichoiceBase(object):
    """
    A base class for widgets that provide the UI to select one or more items
    from a list.

    Based on ChoiceBase

    options:
        A sequence of objects adaptable to IKey and ILabel. IKey is used as the
        <option>'s value attribute; ILabel is used as the <option>'s child.
        IKey and ILabel adapters for tuple are provided.
    noneOption:
        An object adaptable to IKey and ILabel that is used to identify when
        nothing has been selected. Defaults to ('', '')

		default can be whitespace-separated items.
    """

    options = None
    noneOption = None

    def __init__(self, original, options=None, noneOption=_UNSET):
        self.original = original
        if options is not None:
            self.options = options
        if noneOption is not _UNSET:
            self.noneOption = noneOption

    def processInput(self, ctx, key, args, default=''):
        values = args.get(key, default.split())
        rv = []
        for value in values:
            value = iformal.IStringConvertible(self.original).toType(value)
            if self.noneOption is not None and value == self.noneOption[0]:
                value = None
            rv.append(self.original.validate(value))
        return rv

class MultiselectChoice(MultichoiceBase):
    """
    A drop-down list of options.

    <select>
      <option value="...">...</option>
    </select>

    """
    implements( iformal.IWidget )

    noneOption = ('', '')

    def _renderTag(self, ctx, key, value, converter, disabled):

        def renderOptions(ctx, data):
            if self.noneOption is not None:
                yield T.option(value=iformal.IKey(self.noneOption).key())[iformal.ILabel(self.noneOption).label()]
            if data is None:
                return
            for item in data:
                optValue = iformal.IKey(item).key()
                optLabel = iformal.ILabel(item).label()
                optValue = converter.fromType(optValue)
                option = T.option(value=optValue)[optLabel]

                if value and optValue in value:
                    option = option(selected='selected')

                yield option

        tag=T.select(name=key, id=render_cssid(key), data=self.options, multiple="multiple")[renderOptions]

        if disabled:
            tag(class_='disabled', disabled='disabled')
        return tag

    def render(self, ctx, key, args, errors):
        converter = iformal.IStringConvertible(self.original)
        if errors:
            value = args.get(key, [''])
        else:
            value = converter.fromType(args.get(key))
        return self._renderTag(ctx, key, value, converter, False)

    def renderImmutable(self, ctx, key, args, errors):
        converter = iformal.IStringConvertible(self.original)
        value = converter.fromType(args.get(key))
        return self._renderTag(ctx, key, value, converter, True)


__all__ = ["MultichoiceBase", "MultiselectChoice"]
