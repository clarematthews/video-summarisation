import redis
from rq import Worker, Connection

redis_url = 'redis://localhost:6379' 

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(['default'])
        worker.work()
