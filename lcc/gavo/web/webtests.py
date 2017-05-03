"""
A special renderer for testish things requring the full server to be up
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from twisted.internet import reactor

from nevow import inevow
from nevow import rend
from nevow import tags as T

from gavo import base
from gavo.svcs import streaming
from gavo.web import common


class FooPage(rend.Page):
	"""is the most basic page conceivable.
	"""
	docFactory = common.doctypedStan(T.html[
		T.head[
			T.title["A page"],
		],
		T.body[
			T.p["If you see this, you had better know why."]]])


class StreamerPage(rend.Page):
	"""is a page that delivers senseless but possibly huge streams of 
	data through streaming.py
	"""
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		dataSize = int(request.args.get("size", [300])[0])
		chunkSize = int(request.args.get("chunksize", [1000])[0])
		def writeNoise(f):
			for i in range(dataSize/chunkSize):
				f.write("x"*chunkSize)
			lastPayload = "1234567890"
			toSend = dataSize%chunkSize
			f.write(lastPayload*(toSend/10)+lastPayload[:toSend%10])
		return streaming.streamOut(writeNoise, request)


class Delay(rend.Page):
	"""A page returning some data after some time has passed.
	"""
	def renderHTTP(self, ctx):
		from twisted.internet import task
		request = inevow.IRequest(ctx)
		delay = int(request.args.get("seconds", [10])[0])
		request.setHeader("content-type", "text/plain")
		return task.deferLater(reactor, delay, lambda: "Hello world\n")


class Block(rend.Page):
	"""A page blocking the entire server, including signals, for a while.
	"""
	def renderHTTP(self, ctx):
		import os
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/plain")
		os.system("sleep 20")
		return "Living again\n"


class StreamerCrashPage(rend.Page):
	"""is a page that starts streaming out data and then crashes.
	"""
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/plain")
		def writeNoise(f):
			f.buffer.chunkSize = 30
			f.write("Here is some data. (and some more, just to cause a flush)\n")
			raise Exception
		return streaming.streamOut(writeNoise, request)


class ExitPage(rend.Page):
	"""A page that lets the server exit (useful for profiling).
	"""
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/plain")
		reactor.callLater(1, lambda: reactor.stop())
		return "The server is now exiting in 1 second."


class RenderCrashPage(rend.Page):
	"""A page that crashes during render.
	"""
	def render_crash(self, ctx, data):
		try:
			raise Exception("Wanton crash")
		except:
			import traceback
			traceback.print_exc()
			raise

	docFactory = common.doctypedStan(T.html[
		T.head[
			T.title["A page"],
		],
		T.body[
			T.p(render=T.directive("crash"))["You should not see this"]]])


class BadGatewayPage(rend.Page):
	"""A page that returns a 502 error.
	"""
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setResponseCode(502, message="Bad Gateway")
		request.setHeader("content-type", "text/plain")
		return "Bad Gateway"


class ServiceUnloadPage(rend.Page):
	"""a page that clears the services RD.
	"""
	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		request.setHeader("content-type", "text/plain")
		base.caches.clearForName("__system__/services")
		return "Cleared the services RD"



class Tests(rend.Page):
	child_foo = FooPage()
	child_stream = StreamerPage()
	child_streamcrash = StreamerCrashPage()
	child_rendercrash = RenderCrashPage()
	child_badgateway = BadGatewayPage()
	child_block = Block()
	child_exit = ExitPage()
	child_clearservice = ServiceUnloadPage()
	child_delay = Delay()
	docFactory = common.doctypedStan(T.html[
		T.head[
			T.title["Wrong way"],
		],
		T.body[
			T.p["There is nothing here.  Trust me."]]])
