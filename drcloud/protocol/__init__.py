from ..dds import Message


class DrC(Message):
    """Parent of all messages from Dr. Cloud."""
    pass


class Rx(Message):
    """Parent of all messages from the Rx agent to Dr. Cloud."""
    pass
