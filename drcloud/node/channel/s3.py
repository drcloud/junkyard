from collections import namedtuple
import glob
import os

import boto3
from sh import mkdir

from ...anno import computedfield, pre, runonce
from .. import channel
from ...logger import log


class Channel(channel.Channel):
    def __init__(self, root, name, url,
                 aws_access_key_id=None,
                 aws_secret_access_key=None,
                 region_name=None):
        options = {k: v for k, v
                   in [('aws_access_key_id', aws_access_key_id),
                       ('aws_secret_access_key', aws_secret_access_key),
                       ('region_name', region_name)]
                   if v}
        super(Channel, self).__init__(root, name, url, **options)

    def sync(self):
        etag_files = set(self.fslist('etags'))
        for item in self.s3list(self.name, 'i'):
            if item.name in etag_files:
                continue
            etag, data = self.s3get(item.key)
            self.fsput(data, 'i', item.name)
            self.fsput(etag, 'etags', item.name)
        for f in self.fslist('o'):
            if f in etag_files:
                continue
            key = os.path.join(self.prefix, self.name, 'o', f)
            data = self.fsget('o', f)
            etag = self.s3put(key, data)

    def s3list(self, *path):
        pgn = self.s3.get_paginator('list_objects')
        p = os.path.join(self.prefix, *path) + '/'
        for res in pgn.paginate(Bucket=self.bucket, Delimiter='/', Prefix=p):
            if 'Contents' not in res:
                break
            for o in res['Contents']:
                name = o['Key'][len(p):]
                yield Item(name, p, o['ETag'])

    def s3get(self, key):
        result = self.s3.get_object(Bucket=self.bucket, Key=key)
        return (result['ETag'], result['Body'].read())

    def s3put(self, key, data):
        res = self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)
        return res['ETag']

    @runonce
    def setup(self):
        dirs = [self.path('i'), self.path('o'), self.path('etags')]
        log.debug('Setting up directories: %s', ' '.join(dirs))
        mkdir('-p', *dirs)

    @pre(setup)
    def fsput(self, data, *path):
        with open(self.path(*path), 'w+') as h:
            h.write(data)

    @pre(setup)
    def fsget(self, *path):
        with open(self.path(*path)) as h:
            return h.read()

    @pre(setup)
    def fslist(self, *path):
        path = list(path) + ['*']
        return [s.split('/')[-1] for s in glob.glob(self.path(*path))]

    def path(self, *path):
        return os.path.join(self.root, *path)

    @computedfield
    def s3(self):
        return boto3.client('s3', **self.options)

    @computedfield
    def bucket(self):
        return self.url.netloc

    @computedfield
    def prefix(self):
        return self.url.path.strip('/')


class Item(namedtuple('Item', 'name prefix etag')):
    @computedfield
    def key(self):
        return os.path.join(self.prefix, self.name)
