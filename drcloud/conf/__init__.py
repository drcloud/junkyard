from schematics.models import Model
from schematics.types import IntType, StringType, URLType
from schematics.types.compound import ModelType

from .. import logger


class Log(Model):
    syslog = StringType(choices=list(logger.levels()))
    console = StringType(choices=list(logger.levels()))


class Inbox(Model):
    rotation = IntType(min_value=1, max_value=1000000)
    redis = URLType()
    s3 = URLType()
    log = ModelType(Log)


class Agent(Model):
    rotation = IntType(min_value=1, max_value=1000000)
    log = ModelType(Log)


class Node(Model):
    rotation = IntType(min_value=1, max_value=1000000)
    agent = ModelType(Agent)
    inbox = ModelType(Inbox)
    log = ModelType(Log)


class Config(Model):
    node = ModelType(Node)
    log = ModelType(Log)
    conninfo = URLType()
