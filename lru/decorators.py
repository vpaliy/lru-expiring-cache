# -*- coding: utf-8 -*-
"""Cache decorators.

Copyright: (c) 2019 by Vasyl Paliy.
License: MIT, see LICENSE for more details.
"""

import time
import pickle

from hashlib import sha1
from collections import namedtuple
from functools import wraps

from lru import LruCache
from lru.compat import monotonic


def _get_key(function, args, kwargs):
  """Generates a key for a function with its arguments."""
  key = str(args)
  if kwargs:
    for item in kwargs.items():
      key += str(item)
  seed = pickle.dumps((function.__name__, key))
  return sha1(seed).hexdigest()


def lru_cache(maxsize=128, expires=10*60):
  """
  A memoized function, backed by an LRU cache.
  Supports data expiration.

  >>> @lru_cache(maxsize=2, expires=10)
  ... def function(x):
  ...    print "function(" + str(x) + ")"
  ...    return x
  >>> f(3)
  function(3)
  3
  >>> f(5)
  function(5)
  5
  >>> f(3) # the item hasn't expired yet, the wrapped function won't be invoked
  3
  >>> f(5) # the item hasn't expired yet, the wrapped function won't be invoked
  5
  >>> import time
  >>> time.sleep(3) # enough time to remove the first item (3) from the cache
  >>> f(3) # since there is no such item in cache, execute the function again
  function(3)
  3
  >>> time.sleep(2) # enough time to remove the other item (5) from the cache
  >>> f(5) # same thing for 5
  function(5)
  5
  >>> f(3)
  3
  >>> f(4) # the underlying LRU cache will replace 4 with 5
  function(4)
  4
  >>> f(5)
  function(5)
  5
  """
  # create a single cache per function that is being decorated
  cache = LruCache(capacity=maxsize, expires=expires)
  def _lru(function):
    @wraps(function)
    def _lru_wrapper(*args, **kwargs):
      # generate the key
      key = _get_key(function, args, kwargs)
      if key in cache:
        return cache[key]
      result = function(*args, **kwargs)
      cache[key] = result
      return result
    return _lru_wrapper
  return _lru


def _is_stale(entry, time_limit):
  # check if the current entry has expired
  return (monotonic() - entry.time) > time_limit


def _get_lazy_cache():
  return dict()

_Entry = namedtuple('Entry', 'value time')


def lazy_cache(maxsize=128, expires=10*60):
  """
  A memoized function that supports data expiration.
  >>> @lazy_cache(maxsize=128, expires=10)
  ... def function(x):
  ...    print "function(" + str(x) + ")"
  ...    return x
  >>> f(3)
  function(3)
  3
  >>> f(5)
  function(5)
  5
  >>> f(3) # the item hasn't expired yet, the wrapped function won't be invoked
  3
  >>> f(5) # the item hasn't expired yet, the wrapped function won't be invoked
  5
  >>> import time
  >>> time.sleep(3) # enough time to remove the first item (3) from the cache
  >>> f(3) # since there is no such item in cache, execute the function again
  function(3)
  3
  >>> time.sleep(2) # enough time to remove the other item (5) from the cache
  >>> f(5) # same thing for 5
  function(5)
  5
  """
  # for testing purposes
  cache = _get_lazy_cache()
  def _lazy_cache(function):
    @wraps(function)
    def _lazy_cache_wrapper(*args, **kwargs):
      key = _get_key(function, args, kwargs)
      if key in cache:
        if not _is_stale(cache[key], expires):
          return cache[key].value
        del cache[key]
      if len(cache) > maxsize:
        cache.clear()
      result = function(*args, **kwargs)
      cache[key] = _Entry(result, monotonic() + expires)
      return result
    return _lazy_cache_wrapper
  return _lazy_cache
