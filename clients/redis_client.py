from datetime import timedelta
import redis

from framework.configuration.configuration import Configuration
from framework.application.application import get_state
from framework.logger.providers import get_logger

logger = get_logger(__name__)

configuration = get_state(Configuration)
config = configuration.redis


class RedisClient:
    def __init__(self):
        self.cache = redis.Redis(
            host=config.get('host'),
            port=config.get('port'))

    def get(self, key):
        logger.info(f'Get Cache Key: {key}')

        result = self.cache.get(key)
        if result:
            return result.decode()

    def set(self, key, value, lifetime=None):
        exp = timedelta(
            minutes=lifetime or config.get('lifetime'))

        logger.info(f'Set Cache Key: {key} : {value}')
        return self.cache.set(key, value, ex=exp)


redis_client = RedisClient()
