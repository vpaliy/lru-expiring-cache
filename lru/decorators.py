import time
import pickle

from hashlib import sha1
from collections import namedtuple
from functools import wraps
from lru import LruCache


def _get_key(function, args, kwargs):
  key = args
  if kwargs:
    for item in kwargs.items():
      key += item
  seed = pickle.dumps((function.__name__, key))
  return sha1(seed).hexdigest()


def lru_cache(maxsize=128, expires=10*60):
  cache = LruCache(capacity=maxsize, expires=expires)
  def _lru(function):
    @wraps(function)
    def _lru_wrapper(*args, **kwargs):
      key = _get_key(function, args, kwargs)
      if cache.__contains__(key):
        return cache[key]
      result = function(*args, **kwargs)
      cache[key] = result
      return result
    return _lru_wrapper
  return _lru


def _is_stale(entry, time_limit):
  return (time.time() - entry.time) > time_limit


def _get_lazy_cache():
  return dict()

_Entry = namedtuple('Entry', 'value time')


def lazy_cache(maxsize=128, expires=10*60):
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
      cache[key] = _Entry(result, time.time() + expires)
      return result
    return _lazy_cache_wrapper
  return _lazy_cache
