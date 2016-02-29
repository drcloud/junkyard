from ... import logger
from . import s3


def test_s3_works_with_no_input_or_output_on_readonly_bucket():
    chan = s3.Channel('tmp/spools/empty',
                      'test.aws.example.com',
                      's3://drcloud-test/empty/')
    chan.sync()


def setup():
    logger.configure()
