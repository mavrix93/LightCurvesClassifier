"""
A simple caching system for nevow pages.

The basic idea is to monkeypatch the request object in order to
snarf content and headers.
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


import time

from nevow import inevow
from nevow import rend

from gavo import utils


def instrumentRequestForCaching(request, finishAction):
	"""changes request such that finishAction is called with the request and
	the content written for a successful page render.
	"""
	builder = CacheItemBuilder(finishAction)
	request = inevow.IRequest(request)
	origWrite, origFinishRequest = request.write, request.finishRequest

	def write(content):
		builder.addContent(content)
		return origWrite(content)

	def finishRequest(success):
		if success:
			builder.finish(request)
		return origFinishRequest(success)

	request.write = write
	request.finishRequest = finishRequest


class CacheItemBuilder(object):
	"""an aggregator for web pages as they are written.

	On successful page generation an function is called with
	the request and the content written as arguments.
	"""
	def __init__(self, finishAction):
		self.finishAction = finishAction
		self.contentBuffer = []
	
	def addContent(self, data):
		self.contentBuffer.append(data)
	
	def finish(self, request):
		if request.code==200:
			self.finishAction(request, "".join(self.contentBuffer))


class CachedPage(rend.Page):
	def __init__(self, content, headers, lastModified):
		self.content = content
		self.creationStamp = time.time()
		headers["x-cache-creation"] = str(self.creationStamp)
		self.changeStamp = self.lastModified = lastModified
		if "last-modified" in headers:
			del headers["last-modified"]
		self.headers = headers.items()

	def renderHTTP(self, ctx):
		request = inevow.IRequest(ctx)
		if self.lastModified:
			request.setLastModified(self.lastModified)
		for key, value in self.headers:
			request.setHeader(key, value)
		request.setHeader('date', utils.formatRFC2616Date())
		return self.content


def enterIntoCacheAs(key, destDict):
	"""returns a finishAction that enters a page into destDict under key.
	"""
	def finishAction(request, content):
		destDict[key] = CachedPage(content, request.headers, 
			request.lastModified)
	return finishAction
