from .....cloud.aws import Cloud, Service
from ..... import logger


def test_start_and_stop_service():
    cloud = Cloud('aws.example.com')
    service = Service('test', cloud)
    cloud.acquire()
    service.acquire()
    service.release()
    cloud.release()


def setup():
    logger.configure()
