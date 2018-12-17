# -*- coding: future_fstrings -*-
from __future__ import absolute_import

import threading
import time
import weakref

from lru.compat import queue, MutableMapping

_sentinel = object()


def lock(method):
  def _lock(self, *args, **kwargs):
    if hasattr('_lock', self):
      with self._lock:
        return self.method(*args, **kwargs)
    return self.method(*args, **kwargs)
  return _lock


class Node(object):
  __slots__ = ('next', 'prev', 'key',
               'value', 'expires', '__weakref__')

  def __init__(self, key=None, value=None,
               next=None, prev=None, expires=None):
    self.key = key
    self.value = value
    self.next = next
    self.prev = prev
    self.expires = expires

  @property
  def is_expired(self):
    if self.expires is not None:
      return time.now() > self.expires
    return False


class CacheCleaner(threading.Thread):
  daemon = True

  def __init__(self, queue, cache, **kwargs):
    self._queue = queue
    self._cache_ref = weakref.ref(cache)
    self._condition = threading.Condition()
    super(CacheCleaner, self).__init__(**kwargs)

  def run(self):
    queue = self._queue
    condition = self._condition
    while self._cache_ref():
      node = queue.get()
      if node is _sentinel:
        break
      if isinstance(node, Node):
        with condition:
          while not node.is_expired:
            condition.wait(node.expires)
          queue.task_done()
          cache = self._cache_ref()
          if cache is not None:
            del cache[node.key]


class LRUCache(MutableMapping):
  def __init__(*args, **kwargs):
    if not args:
      raise TypeError('__init__() needs an argument')
    self, args = args[0], args[1:]
    kwargs = kwargs or {'capacity':10}
    if kwargs.setdefault('capacity', 10) <= 0:
      raise ValueError('capacity should not be less than or equal to 0')
    try:
      self._capacity
    except AttributeError:
      self._capacity = kwargs['capacity']
      self._hardroot = Node()
      root = self._root = weakref.proxy(self._hardroot)
      root.next = root.prev = root
      self._mapping = {}
      if 'expires' in kwargs:
        self._expires = kwargs.get('expires')
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._init_cleaner()
    del kwargs['capacity']
    self.update(*args, **kwargs)

  def _init_cleaner(self):
    cleaner = CacheCleaner(self._queue, self)
    cleaner.start()

  def _bump_up(self, node):
    root = self._root
    if root.next is not node:
      next, prev = node.next, node.prev
      next.prev = prev
      prev.next = next
      self._connect_with_root(node)

  def _connect_with_root(self, node):
    root = self._root
    node.prev, node.next = root, root.next
    root.next.prev = node
    root.next = node

  @lock
  def __getitem__(self, key):
    node = self._mapping[key]
    self._bump_up(node)
    return node.value

  def __setitem__(self, key, value):
    self.add(key, value)

  @lock
  def add(self, key, value, expires=None):
    if any([key is None, value is None]):
      raise TypeError
    if key in self._mapping:
      node = self._mapping[key]
      node.value = value
      self._bump_up(node)
      return
    if len(self._mapping) > self._capacity:
      del self[self._root.prev.key]
    if expires is None:
      expires = getattr(self, 'expires', None)
    node = Node(key, value, expires=expires)
    self._mapping[key] = node
    self._connect_with_root(node)

  @property
  def expires(self):
    if self.expires is not None:
      return time.now() + self.expires
    return None

  @lock
  def __delitem__(self, key):
    node = self._mapping.pop(key)
    next, prev = node.next, node.prev
    next.prev = prev
    prev.next = next
    node.next = node.prev = None

  def __iter__(self):
    return iter(self.values())

  @lock
  def __contains__(self, key):
    return key in self._mapping

  @lock
  def __len__(self):
    return len(self._mapping)

  @lock
  def __eq__(self, other):
    if isinstance(other, LRUCache):
      if len(other) == len(self):
        node = self._root.next
        for key, value in other.items():
          if (key != node.key) or (value != node.value):
            return False
          node = node.next
        return True
    return False

  def keys(self):
    return [node.key for node in self._iterator()]

  def values(self):
    return [node.value for node in self._iterator()]

  def items(self):
    return [(node.key, node.value)
        for node in self._iterator()]

  def clear(self):
    for key in self.keys():
      del self[key]

  def copy(self):
    return LRUCache(self.items()[::-1])

  @lock
  def _iterator(self):
    root = self._root
    node = root.next
    while node is not root:
      next = node.next
      yield node
      node = next

  @lock
  def update(*args, **kwargs):
    if not args:
      raise TypeError('`update()` takes an argument')
    self, args = args[0], args[1:]
    if len(args) > 1:
      raise TypeError('`update()` takes at most 1 argument')
    if args:
      other = args[0]
      if hasattr(other, 'keys'):
        for key in other.keys():
          self[key] = other[key]
      elif isinstance(other, MutableMapping):
        for key, value in other.items():
          self[key] = value
      else:
        for key, value  in other:
          self[key] = value
    if kwargs is not None:
      for key, value in kwargs.items():
        self[key] = value

  def __repr__(self):
    return '\n'.join((f'{k}:{v}' for k, v in self.items()))
