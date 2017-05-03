"""
A cron-like facility to regularly run some functions.

Most of the apparatus in here is not really for user consumption.
There's a singleton of the queue created below, and the methods of that
singleton are exposed as module-level functions.

To make the jobs actually execute, the running program has to call 
registerSchedulerFunction(schedulerFunction).  Only the first 
registration is relevant.  The schedulerFunction has the signature 
sf(delay, callable) and has to arrange for callable to be called delay 
seconds in the future; twisted's reactor.callLater works like this.

However, you should arrange for previous callLaters to be canceled when 
a new one comes in.  There is no management to make sure only one
queue reaper runs at any time (it doesn't hurt much if more than one
run, but it's a waste of resources).
"""

#c Copyright 2008-2014, the GAVO project
#c
#c This program is free software, covered by the GNU GPL.  See the
#c COPYING file in the source distribution.


from __future__ import with_statement

import calendar
import datetime
import heapq
import sys
import subprocess
import time
import threading
import traceback

from gavo import utils
from gavo.base import config


def sendMailToAdmin(subject, message):
	"""tries to send a mail to the configured administrator.

	This relies on a functional mail infrastructure on the local host.
	"""
	if not config.get("maintainerAddress"):
		utils.sendUIEvent("Error", "Wanted to send mail with subject '%s', but no"
			" maintainerAddress is given"%subject)
		return

	pipe = subprocess.Popen(config.get("sendmail"), shell=True,
		stdin=subprocess.PIPE)
	pipe.stdin.write("\n".join(["To: "+config.get("maintainerAddress"),
		"Subject: "+subject,
		"From: DaCHS server <%s>"%config.get("maintainerAddress"),
		"Content-Type: text/plain",
		"",
		utils.safe_str(message)]))
	pipe.stdin.close()

	if pipe.wait():
		utils.sendUIEvent("Error", "Wanted to send mail with subject"
			"'%s', but sendmail returned an error message"
			" (check the [general]sendmail setting)."%subject)


class AbstractJob(object):
	"""A job run in a queue.

	These have a name and a run() method; use their reportCronFailure(message)
	method to deliver error messages (of course, you can also just log;
	reportCronFailure will in typically send a mail).  Concrete jobs
	have to implement a getNextWakeupTime(gmtime) -> gmtime method;
	they probably have to redefine __init__; the must up-call.
	"""
	# here, Queue keeps track of the last time this job was started.
	lastStarted = None

	def __init__(self, name, callable):
		self.name = name
		self.callable = callable

	def __str__(self):
		return "<%s %s, last run at %s>"%(
			self.__class__.__name__, self.name, self.lastStarted)

	def reportCronFailure(self, message):
		sendMailToAdmin("DaCHS %s job failed"%self.name,
			"\n".join([
				"DaCHS job %s failed"%utils.safe_str(self),
				"\nDetails:\n",
				message]))

	def run(self):
		"""runs callable under somewhat reliable circumstances.
		"""
		try:
			self.callable()
		except Exception:
			utils.sendUIEvent("Error",
				"Failure in timed job %s.  Trying to send maintainer a mail."%
					utils.safe_str(self))
			self.reportCronFailure("".join(
				traceback.format_exception(*sys.exc_info())))

	def getNextWakeupTime(self, curTime):
		"""returns the UTC unix epoch seconds when this job is next
		supposed to run, starting from curTime.
		"""
		raise NotImplementedError(
			"You must override AbstractJob.getNextWakeupTime()")


class IntervalJob(AbstractJob):
	"""A job that's executed roughly every interval seconds.
	"""
	def __init__(self, interval, name, callable):
		self.interval = interval
		AbstractJob.__init__(self, name, callable)

	def getNextWakeupTime(self, curTime):
		if self.lastStarted is None:
			return curTime+self.interval/10
		else:
			return curTime+self.interval


class DailyJob(AbstractJob):
	"""A job that's run roughly daily at some wallclock (UTC) times.

	times is a list of (hour, minute) pairs.
	"""
	def __init__(self, times, name, callable):
		self.times = times
		AbstractJob.__init__(self, name, callable)

	def getNextWakeupTime(self, curTime):
		# dumb strategy: get parts, replace hour and minute, and if it's
		# in the past, add a day; do that for all recurrence times, and use
		# the smallest one.
		nextWakeups = []
		curTup = time.gmtime(curTime)
		for hour, minute in self.times:
			wakeupTime = calendar.timegm(
				curTup[:3]+(hour, minute)+curTup[5:])
			if wakeupTime<curTime:
				wakeupTime += 86400
			nextWakeups.append(wakeupTime)
		return min(nextWakeups)


class Queue(object):
	"""A cron-job queue.

	This is really a heap sorted by the time the job is next supposed to run.
	"""
	def __init__(self):
		self.jobs = []
		self.lock = threading.Lock()
		self.scheduleFunction = None

	def _rescheduleJob(self, job):
		"""adds job to the queue and reschedules the wakeup if necessary.
		
		Since this method does not check for the presence of like-named jobs,
		it must be used for rescheduling exclusively.  To schedule new jobs,
		use _scheduleJob.
		"""
		with self.lock:
			heapq.heappush(self.jobs, (job.getNextWakeupTime(time.time()), job))
		self._scheduleWakeup()

	def _scheduleJob(self, job):
		"""adds job to the job list.

		This is basically like _rescheduleJob, except that this method makes
		sure that any other job with the same name is removed.
		"""
		lastStarted = self._unscheduleForName(job.name)
		job.lastStarted = lastStarted
		self._rescheduleJob(job)

	def _unscheduleForName(self, name):
		"""removes all jobs named name from the job queue.
		"""
		toRemove = []
		with self.lock:
			for index, (_, job) in enumerate(self.jobs):
				if job.name==name:
					toRemove.append(index)
			if not toRemove:
				return None

			toRemove.reverse()
			retval = self.jobs[toRemove[0]][1].lastStarted
			for index in toRemove:
				self.jobs.pop(index)
			heapq.heapify(self.jobs)
		return retval

	def _runNextJob(self):
		"""takes the next job off of the job queue and runs it.

		If the wakeup time of the next job is too far in the future,
		this does essentially nothing.
		"""
		with self.lock:
			if not self.jobs:
				return
			jobTime, job = heapq.heappop(self.jobs)

		try:
			if jobTime>time.time()+1:
				# spurious wakeup, forget about it
				pass
			else:
				job.lastStarted = time.time()
				job.run()
		finally:
			self._rescheduleJob(job)
	
	def _scheduleWakeup(self):
		"""makes the toplevel scheduler wake queue processing up when the
		next job is due.
		"""
		if not self.jobs:  
			# Nothing to run; we'll be called when someone schedules something
			return
		nextWakeup = self.jobs[0][0]
		if self.scheduleFunction is not None:
			self.scheduleFunction(max(0, nextWakeup-time.time()), self._runNextJob)

	def runEvery(self, seconds, name, callable):
		"""schedules callable to be run every seconds.

		name must be a unique identifier for the "job".  jobs with identical
		names overwrite each other.

		callable will be run in the main thread, so it must finish quickly
		or it will block the server.
		"""
		self._scheduleJob(IntervalJob(seconds, name, callable))

	def repeatAt(self, times, name, callable):
		"""schedules callable to be run every day at times.

		times is a list of (hour, minute) pairs.

		name must be a unique identifier for the "job".  jobs with identical
		names overwrite each other.

		callable will be run in the main thread, so it must finish quickly
		or it will block the server.
		"""
		self._scheduleJob(DailyJob(times, name, callable))

	def registerScheduleFunction(self, scheduleFunction):
		if self.scheduleFunction is None:
			self.scheduleFunction = scheduleFunction
			self._scheduleWakeup()

	def clearScheduleFunction(self):
		self.scheduleFunction = None

	def getQueueRepr(self):
		"""returns a sequence of (startDateTime local, job name) pairs.

		This is for inspection/debug purposes.
		"""
		with self.lock:
			schedule = self.jobs[:]
		return [(datetime.datetime.fromtimestamp(jobTime), job.name)
			for jobTime, job in schedule]


_queue = Queue()
runEvery = _queue.runEvery
repeatAt = _queue.repeatAt
registerScheduleFunction = _queue.registerScheduleFunction
clearScheduleFunction = _queue.clearScheduleFunction
