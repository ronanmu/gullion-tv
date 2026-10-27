"""Run slow work (network, disk) off the screen thread and hand the result back on it.

enigma2's screens may only be touched from the main thread, so a timer checks
for finished jobs and calls each job's done(result, error) from there.
"""
import threading

from enigma import eTimer


class Background(object):
	def __init__(self, interval=200):
		self.interval = interval
		self.jobs = []
		self.timer = eTimer()
		self.timer.callback.append(self.poll)

	def run(self, work, done):
		job = {"done": done, "finished": False, "result": None, "error": None}

		def target():
			try:
				job["result"] = work()
			except Exception as error:
				job["error"] = error
			job["finished"] = True

		job["thread"] = threading.Thread(target=target)
		job["thread"].daemon = True
		self.jobs.append(job)
		job["thread"].start()
		self.timer.start(self.interval, False)

	def poll(self):
		for job in [job for job in self.jobs if job["finished"]]:
			self.jobs.remove(job)
			job["done"](job["result"], job["error"])
		if not self.jobs:
			self.timer.stop()

	def wait(self, timeout=10):
		"""Finish every job now. For tools/check.py, which has no running timer."""
		while self.jobs:
			for job in list(self.jobs):
				job["thread"].join(timeout)
			self.poll()

	def stop(self):
		self.timer.stop()
		del self.jobs[:]
