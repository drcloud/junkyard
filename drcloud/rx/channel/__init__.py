from urlparse import ParseResult, urlparse


class Channel(object):
    def __init__(self, root, name, url, **options):
        self.root = root
        self.name = name
        if not isinstance(url, ParseResult):
            url = urlparse(url)
        self.url = url
        self.options = options

    def sync(self):
        raise NotImplementedError()
