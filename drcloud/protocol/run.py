"""The ``run`` protocol describes how nodes run one-off tasks.
"""
from schematics.models import Model
from schematics.types import DateTimeType, StringType, UUIDType
from schematics.types.compound import ListType, ModelType

from . import DrC, Rx
from ..task import Task
from ..status import StatusType


class Run(DrC):
    """Dr. Clouds sends a task to run."""
    uuid = UUIDType(required=True)
    task = ModelType(Task, required=True)


class TSLine(Model):
    t = DateTimeType(required=True)
    s = StringType(required=True)


class Status(Rx):
    """A node responds with the status of the run."""
    uuid = UUIDType(required=True)
    status = StatusType(required=True)
    message = StringType()
    o = ListType(ModelType(TSLine), max_size=128)
    e = ListType(ModelType(TSLine), max_size=128)

    class Options:
        serialize_when_none = False
