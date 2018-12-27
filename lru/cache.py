# -*- coding: future_fstrings -*-
from __future__ import absolute_import

import threading
import time
import weakref

from functools import total_ordering
from lru.compat import queue, MutableMapping

_sentinel = object()
_infinite = object()


def lock(method):
  def _lock(self, *args, **kwargs):
    if hasattr(self, '_lock'):
      with self._lock:
        return method(self, *args, **kwargs)
    return method(self, *args, **kwargs)
  return _lock


class _Node(object):
  __slots__ = ('next', 'prev', 'key',
               'value', '__weakref__')

  def __init__(self, key=None, value=None,
               next=None, prev=None, expires=None):
    self.key = key
    self.value = value
    self.next = next
    self.prev = prev


@total_ordering
class _ExpNode(_Node):
  __slots__ =  ('expires', )

  def __init__(self, expires=None, *args, **kwargs):
    super(_ExpNode, self).__init__(*args, **kwargs)
    self.expires = expires

  @property
  def remaining(self):
    return self.expires - time.time()

  @property
  def is_expired(self):
    return time.time() > self.expires

  def __eq__(self, other):
    if not isinstance(other, _ExpNode):
      raise TypeError('Invalid type')
    return self.expires == other.expires

  def __lt__(self, other):
    if not isinstance(other, _ExpNode):
      raise TypeError('Invalid type')
    return self.expires > other.expires


def _create_node(key=None, value=None, next=None, prev=None, expires=None):
  if expires is not None:
    return _ExpNode(**locals())
  return _Node(**locals())


class CacheCleaner(threading.Thread):
  daemon = True

  def __init__(self, queue, cache, condition, **kwargs):
    self._queue = queue
    self._cache_ref = weakref.ref(cache)
    self._condition = condition
    super(CacheCleaner, self).__init__(**kwargs)

  def run(self):
    queue = self._queue
    condition = self._condition
    while self._cache_ref():
      node = queue.get()
      if node is _sentinel:
        break
      if isinstance(node, _ExpNode):
        with condition:
          while node and (not node.is_expired):
            condition.wait(node.remaining)
            try:
              fast = queue.get_nowait()
              if (fast and node) and (fast < node):
                queue.put(node)
                node = fast
            except queue.Empty:
              pass
          queue.task_done()
          cache = self._cache_ref()
          if cache and node:
            del cache[node.key]


class CleanManager(object):
  def __init__(self, cache):
    self._queue = queue.PriorityQueue()
    self._condition = threading.Condition()
    self._cache_cleaner = CacheCleaner(
      self._queue, cache, self._condition
    )
    self._initialized = False

  def add(self, node):
    if isinstance(node, _ExpNode):
      if not self._initialized:
        self._initialized = True
        self._cache_cleaner.start()
      print(node)
      node = weakref.proxy(node)
      self._queue.put(node)
      if self._condition._is_owned():
        self._condition.notify()

  def on_delete(self):
    if self._condition._is_owned():
      self._condition.notify()


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
      self._hardroot = _Node()
      root = self._root = weakref.proxy(self._hardroot)
      root.next = root.prev = root
      self._mapping = {}
      if 'expires' in kwargs:
        self._expires = kwargs['expires']
        self._init_cleaner()
    del kwargs['capacity']
    self.update(*args, **kwargs)

  def _init_cleaner(self):
    self._cleaner = CleanManager(self)
    self._lock = threading.RLock()

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
    if expires is None:
      expires = getattr(self, 'expires', None)
    if key in self._mapping:
      node = self._mapping[key]
      del self[node.key]
    if len(self._mapping) > self._capacity:
      del self[self._root.prev.key]
    node = _create_node(key, value, expires=expires)
    self._mapping[key] = node
    self._connect_with_root(node)
    if expires and not hasattr(self, '_cleaner'):
      self._init_cleaner()
    if hasattr(self, '_cleaner'):
      self._cleaner.add(node)

  @property
  def expires(self):
    if self._expires is not None:
      return time.time() + self._expires
    return _infinite

  @lock
  def __delitem__(self, key):
    node = self._mapping.pop(key)
    next, prev = node.next, node.prev
    next.prev = prev
    prev.next = next
    node.next = node.prev = None; del node
    if hasattr(self, '_cleaner'):
      self._cleaner.on_delete()

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
