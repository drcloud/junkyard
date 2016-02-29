"""Annotate methods with SQL queries, drawn from a SQL file.

SQL queries in a SQL file can be attached to empty methods in a class
definition using this module.

The class to be annotated must subclass `Queries` from this module.

In the SQL file, every block that is marked with ``--@ <name> <mode>`` is
treated as a distinct query. The blocks may be any number of SQL statements.
An example mark is ``--@ check_up ~``. The ``<name>`` should be a Python name,
the ``<mode>`` should be one of:

``~``
    Indicates there should never be any result rows. The return value is `None`
    or an assertion error is thrown.

``?``
    Indicates there should be one or zero result rows. A single row or `None`
    is returned.

``!``
    Indicates there should always be one result row. A single row is returned
    or an assertion error is thrown.

``*``
    Indicates there may be multiple rows returned. An array (possibly empty) of
    rows is returned.

"""
from collections import OrderedDict
from functools import wraps
import inspect
import logging
import pkg_resources
import re

from oset import oset
import sqlparse
from sqlparse.sql import Comment

from .pg import PG


log = logging.getLogger(__name__)


class Queries(object):
    def __init__(self, dsn, logger=None):
        logger = logger or log
        self._pg = PG(dsn, logger=logger)
        self._first = True

    def _run_tilde(self, query, params):
        if self._first:
            self._first = False
            if hasattr(self, 'init'):
                self.init()
        with self._pg.txn() as txn:
            txn.execute(query, params)
            assert txn.rowcount < 0

    def _run_question(self, query, params):
        if self._first:
            self._first = False
            if hasattr(self, 'init'):
                self.init()
        with self._pg.txn() as txn:
            txn.execute(query, params)
            assert txn.rowcount <= 1
            if txn.rowcount > 0:
                return txn.fetchone()

    def _run_bang(self, query, params):
        if self._first:
            self._first = False
            if hasattr(self, 'init'):
                self.init()
        with self._pg.txn() as txn:
            txn.execute(query, params)
            assert txn.rowcount == 1
            return txn.fetchone()

    def _run_star(self, query, params):
        if self._first:
            self._first = False
            if hasattr(self, 'init'):
                self.init()
        with self._pg.txn() as txn:
            txn.execute(query, params)
            assert txn.rowcount >= 0
            return txn.fetchall()


class Annotator(object):
    def __init__(self, grouped_statements):
        if isinstance(grouped_statements, basestring):
            grouped_statements = translate_query_signatures(
                group_queries(obtain_sql(grouped_statements))
            )
        self._statements = OrderedDict((name, (args, mode, text))
                                       for name, args, mode, text
                                       in grouped_statements)

    def sql(self, method):
        query_params, mode, query = self._statements[method.__name__]
        argspec = inspect.getargspec(method)
        self_name = argspec.args[0]
        method_args = set(argspec.args[1:] + (argspec.keywords or []))
        query_params = set(query_params)

        if query_params != method_args:
            raise TypeError('Method %s(%s) and query %s(%s) have incompatible '
                            'signatures.' % (method.__name__,
                                             ','.join(sorted(method_args)),
                                             method.__name__,
                                             ','.join(sorted(query_params))))

        assert mode in ['~', '?', '!', '*']

        if mode == '~':
            @wraps(method)
            def f(queries_instance, *args, **kwargs):
                as_kw_params = inspect.getcallargs(method, queries_instance,
                                                   *args, **kwargs)
                del as_kw_params[self_name]
                return queries_instance._run_tilde(query, as_kw_params)
            return f

        if mode == '?':
            @wraps(method)
            def f(queries_instance, *args, **kwargs):
                as_kw_params = inspect.getcallargs(method, queries_instance,
                                                   *args, **kwargs)
                del as_kw_params[self_name]
                return queries_instance._run_question(query, as_kw_params)
            return f

        if mode == '!':
            @wraps(method)
            def f(queries_instance, *args, **kwargs):
                as_kw_params = inspect.getcallargs(method, queries_instance,
                                                   *args, **kwargs)
                del as_kw_params[self_name]
                return queries_instance._run_bang(query, as_kw_params)
            return f

        if mode == '*':
            @wraps(method)
            def f(queries_instance, *args, **kwargs):
                as_kw_params = inspect.getcallargs(method, queries_instance,
                                                   *args, **kwargs)
                del as_kw_params[self_name]
                return queries_instance._run_star(query, as_kw_params)
            return f


def obtain_sql(file):
    return sqlparse.parse(pkg_resources.resource_string(__package__, file))


def group_queries(statements):
    tokens = [token for statement in statements for token in statement.tokens]
    current = None
    mode = None
    group = ''
    for token in tokens:
        if isinstance(token, Comment) and token.value.startswith('--@ '):
            if current is not None:
                yield current, mode, group.rstrip()
            assert token.value.endswith('\n')
            info = token.value.strip().split(' ')
            assert len(info) <= 3
            if len(info) == 3:
                current, mode = info[1:]
            else:
                current, mode = info[1], '*'
            group = ''
            continue
        if current is None:
            continue
        group += token.value
    yield current, mode, group.rstrip()


def translate_query_signatures(grouped):
    for query_name, mode, text in grouped:
        yield query_name, percent_expansions(text), mode, text


def percent_expansions(text):
    references = oset(re.findall('%[(][a-zA-Z_][a-zA-Z0-9_]*[)]s', text))
    return [s.split('(')[1].split(')')[0] for s in references]


# Recognize ``%(param)s`` style references used by PsycoPG
param_reference = re.compile('%[(][a-zA-Z_][a-zA-Z0-9_]*[)]s')

