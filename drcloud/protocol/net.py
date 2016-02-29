"""The ``net`` protocol describes how nodes are updated with routes and names.
"""
import uuid

from schematics.types import StringType, UUIDType
from schematics.types.compound import ListType, ModelType

from . import DrC, Rx


zero = uuid.UUID('00000000-0000-0000-0000-000000000000')

statuses = set('waiting started finished failed'.split())


class Spec(DrC):
    """Dr. Clouds sends network info to a node."""
    revision = UUIDType(required=True)
    network = ModelType(required=True)


class Status(Rx):
    """A node responds with the status of the update."""
    revision = UUIDType(required=True, default=zero)
    status = StringType(required=True, choices=list(statuses))
    message = StringType(required=True, max_length=512)


class Report(DrC):
    """Dr. Cloud requests information about a node's network."""
    since = UUIDType(required=True, default=zero)


class State(Rx):
    """A node sends its network information to Dr. Cloud."""
    revisions = ListType(UUIDType(), max_size=16)
    network = ModelType(required=True)
