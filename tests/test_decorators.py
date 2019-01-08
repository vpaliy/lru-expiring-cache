# -*- coding: future_fstrings -*-
import os
import sys
import unittest
try:
  import unittest.mock as mock
except ImportError:
  import mock

from lru import lru_cache, lazy_cache

_mock_func = mock.Mock()
# Python 2 raises an exception if not provided
_mock_func.__name__ = 'MockFunc'

def _prepare(func, *args, **kwargs):
  return func(*args, **kwargs)(_mock_func)


def _reset(*mocks):
  for mock in mocks:
    mock.reset_mock()


class DummyEntry(object):
  def __init__(self, value):
    self.value = value


class CacheDecoratorsTestCase(unittest.TestCase):
  @mock.patch('lru.decorators.LruCache', autospec=True)
  @mock.patch('lru.decorators._get_key', autospec=True)
  def test_lru_cache(self, get_key_mock, LruCacheMock):
    # dummy inputs
    key, value = tuple(range(2))
    _mock_func.reset_mock()
    # set up mocks
    cache = LruCacheMock()
    cache.__contains__.return_value = True
    cache.__getitem__.return_value = value
    get_key_mock.return_value = key
    _mock_func.return_value = value
    function = _prepare(lru_cache)

    # 1 test case
    # key is in cache, return it
    self.assertEqual(function(key), value)

    cache.__contains__.assert_called_once_with(key)
    cache.__getitem__.assert_called_once_with(key)
    get_key_mock.assert_called_once_with(_mock_func, (key,), {})
    _mock_func.assert_not_called()

    # 2 case
    # key is not in cache
    # call the function, cache the result, return it
    _reset(get_key_mock, cache)
    cache.__contains__.return_value = False

    self.assertEqual(function(key), value)

    cache.__contains__.assert_called_once_with(key)
    cache.__setitem__.assert_called_once_with(key, value)
    get_key_mock.assert_called_with(_mock_func, (key,), {})
    _mock_func.assert_called_with(key)


  @mock.patch('lru.decorators._get_key', autospec=True)
  @mock.patch('lru.decorators._is_stale', autospec=True)
  @mock.patch('lru.decorators._get_lazy_cache', autospec=True)
  def test_lazy_cache(self, get_cache_mock, is_stale_mock, get_key_mock):
    # dummy inputs
    cache = mock.MagicMock()
    key, value = tuple(range(2))
    _reset(_mock_func)

    # setting up mocks
    get_key_mock.return_value = key
    get_cache_mock.return_value = cache
    _mock_func.return_value = value
    cache.__contains__.return_value = False
    function = _prepare(lazy_cache)

    # 1 test case
    # not in cache, execute the function, return the result
    self.assertEqual(function(key), value)

    get_key_mock.assert_called_once_with(_mock_func, (key,), {})
    cache.__contains__.assert_called_once_with(key)
    cache.__getitem__.assert_not_called()
    cache.__setitem__.assert_called_once()
    _mock_func.assert_called_once_with(key)


    # 2 test case
    # in cache, not stale
    _reset(_mock_func, get_key_mock, is_stale_mock, cache)
    is_stale_mock.return_value = False
    cache.__contains__.return_value = True
    cache.__getitem__.return_value = DummyEntry(value)

    self.assertEqual(function(key), value)

    get_key_mock.assert_called_with(_mock_func, (key,), {})
    cache.__contains__.assert_called_once_with(key)
    # should be called twice with the  same key
    cache.__getitem__.assert_called_with(key)
    cache.__setitem__.assert_not_called()
    _mock_func.assert_not_called()


    # 3 test case
    # in cache but stale
    _reset(_mock_func, get_cache_mock, get_key_mock, is_stale_mock, cache)

    is_stale_mock.return_value = True

    function = _prepare(lazy_cache)
    self.assertEqual(function(key), value)

    cache.__delitem__.assert_called_once_with(key)
    cache.__contains__.assert_called_once_with(key)
    cache.__setitem__.assert_called_once()
    _mock_func.assert_called_once_with(key)
    get_key_mock.assert_called_with(_mock_func, (key,), {})

    # 4 test case
    # clear the cache
    _reset(_mock_func, get_cache_mock, get_key_mock, is_stale_mock, cache)
    maxsize = 10
    cache.__contains__.return_value = True
    cache.__len__.return_value = maxsize + 1
    function = _prepare(lazy_cache, maxsize=maxsize)

    self.assertEqual(function(key), value)
    cache.__contains__.assert_called_once_with(key)
    cache.__len__.assert_called_once()
    cache.__setitem__.assert_called_once()
    _mock_func.assert_called_once_with(key)
    get_key_mock.assert_called_with(_mock_func, (key,), {})


def main():
  unittest.main()

if __name__ == '__main__':
  main()
