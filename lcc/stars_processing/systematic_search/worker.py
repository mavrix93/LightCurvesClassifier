
import multiprocessing
import os

import redis
from rq import Worker

import keras

connection = redis.Redis(host=os.environ.get("LCC_REDIS_HOST", "localhost"),
                         port=os.environ.get("LCC_REDIS_PORT", 6379))


def run_worker(burst=False):
    w = Worker(queues=[os.environ.get("LCC_QUEUE_NAME", "lcc")], connection=connection)
    w.work(burst=burst)


def run_workers(n_workers=None, burst=False):
    if not n_workers:
        n_workers = int(os.environ.get("LCC_WORKERS_NUM", "4"))
    jobs = [multiprocessing.Process(target=run_worker, args=(burst,)) for _ in range(n_workers)]

    for i in range(len(jobs)):
        print("Running the worker {}..".format(i))
        jobs[i].start()


if __name__ == '__main__':
    run_workers()


