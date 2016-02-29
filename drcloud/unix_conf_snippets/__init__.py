import pkg_resources


def fetch(filename):
    """
    :type filename: str
    """
    data = pkg_resources.resource_string(__package__, filename)
    return data.strip() + '\n'
