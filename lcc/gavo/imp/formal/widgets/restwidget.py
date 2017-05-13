"""
ReST text area widget.
"""

from nevow import inevow, loaders, rend, tags as T
from gavo.imp.formal import iformal, widget
from gavo.imp.formal.util import render_cssid
from gavo.imp.formal.form import widgetResourceURLFromContext


class ReSTTextArea(widget.TextArea):
    """
    A large text entry area that accepts ReST and previews it as HTML
    This will accept a restWriter parameter
    """

    restWriter = None

    def __init__(self, original, **kwds):
        restWriter = kwds.pop('restWriter', None)
        super(ReSTTextArea, self).__init__(original, **kwds)
        if restWriter is not None:
            self.restWriter = restWriter

    def _renderTag(self, ctx, key, value, readonly):
        tag=T.invisible()
        ta=T.textarea(name=key, id=render_cssid(key), cols=self.cols, rows=self.rows)[value or '']
        if readonly:
            ta(class_='readonly', readonly='readonly')
        tag[ta]

        if not readonly:
            try:
                import docutils
            except ImportError:
                raise
            else:
                form = iformal.IForm( ctx )
                srcId = render_cssid(key)
                previewDiv = render_cssid(key, 'preview-div')
                frameId = render_cssid(key, 'preview-frame')
                targetURL = widgetResourceURLFromContext(ctx, form.name).child(key).child( srcId )
                tag[T.br()]
                onclick = ["return Forms.Util.previewShow('",previewDiv, "', '",
                        frameId, "', '", targetURL, "');"]
                tag[T.button(onclick=onclick)['Preview ...']]
                tag[T.div(id=previewDiv, class_="preview-hidden")[
                        T.iframe(class_="preview-frame", name=frameId, id=frameId),
                        T.br(),
                        T.button(onclick=["return Forms.Util.previewHide('", previewDiv, "');"])['Close']
                    ]
                ]

        return tag

    def getResource(self, ctx, key, segments):
        return ReSTPreview(ctx, self.restWriter, key, segments[0]), segments[1:]


class ReSTPreview(rend.Page):

    def __init__(self, ctx, restWriter, key, srcId):
        self.restWriter = restWriter

        form = iformal.IForm( ctx )
        u = widgetResourceURLFromContext(ctx, form.name).child(key).child( srcId ).child('_submit')
        self.destId=srcId + '-dest'
        formId=srcId + '-form'

        stan = T.html()[
            T.head()[
                T.script(type="text/javascript")["""
                function ReSTTranslate() {
                    dest = document.getElementById('%(destId)s');
                    form = document.getElementById('%(formId)s');
                    src = parent.document.getElementById('%(srcId)s');
                    dest.value = src.value;
                    form.submit(); 
                }    

                """%{'srcId':srcId, 'destId':self.destId, 'formId':formId}]
            ],
            T.body()[
                T.form(id=formId, method="POST", action=u)[
                    T.input(type="hidden", name=self.destId, id=self.destId)
                ],
                T.script(type="text/javascript")["ReSTTranslate();"],
            ],
        ]

        self.docFactory = loaders.stan(stan)

    def child__submit(self, ctx):
        args = inevow.IRequest(ctx).args
        value = args.get(self.destId, [''])[0]

        from docutils.utils import SystemMessage

        try:
            if self.restWriter:
                restValue = self._html_fragment(value, writer=self.restWriter)
            else:
                restValue = self._html_fragment(value, writer_name='html')
        except SystemMessage, e:
            restValue = str(e)

        stan = T.html()[
            T.head()[
                T.style(type="text/css")["""
                
                    .system-message {border: 1px solid red; background-color: #FFFFDD; margin: 5px; padding: 5px;}
                    .system-message-title { font-weight: bold;}
                """
                ]
            ],
            T.body()[
                T.div()[
                    T.xml(restValue)
                ]
            ],
        ]

        self.docFactory = loaders.stan(stan)

        return self
    
    def _html_fragment(self, input_string, writer=None, writer_name=None):
        from docutils.core import publish_parts

        overrides = {'input_encoding': 'utf8',
                     'doctitle_xform': 0,
                     'initial_header_level': 1}
        parts = publish_parts(
            source=input_string, 
            writer_name=writer_name, writer=writer, settings_overrides=overrides)
        fragment = parts['fragment']
        return fragment.encode('utf8')


__all__ = ['ReSTTextArea']
