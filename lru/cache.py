# -*- coding: future_fstrings -*-
# -*- coding: utf-8 -*-

"""LRU cache.

Copyright: (c) 2019 by Vasyl Paliy.
License: MIT, see LICENSE for more details.
"""

from __future__ import absolute_import
from __future__ import with_statement

import threading
import time
import weakref

from functools import total_ordering, wraps
from lru.compat import queue, MutableMapping

# internal objects

_sentinel = object()

_DEFAULT_CACHE_SIZE = 128


def lock(method):
  """A decorator that prevents a potential race condition scenario.
  Must be used by all methods in a multi-threaded environment.

  :param func: a method which has to acquire RLock if applicable.
  :return _lock: a wrapper that determines whether to apply
    RLock before executing the function or not.
  """
  def _lock(self, *args, **kwargs):
    # we need a lock per class
    if hasattr(self, '_lock'):
      with self._lock:
        return method(self, *args, **kwargs)
    return method(self, *args, **kwargs)
  return _lock


class _Node(object):
  """Encapsulates the essential state of each item that is being cached.
  Serves as the fundamental building block of the internal linked list
  in every LRU cache instance. The primary objective of the linked list
  is to keep the most commonly used items in the front while pushing the
  least used items to the end of the list.
  """

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
  """An extension to the _Node class with an expiration date."""

  __slots__ =  ('expires', )

  def __init__(self, expires=None, *args, **kwargs):
    super(_ExpNode, self).__init__(*args, **kwargs)
    self.expires = expires

  @property
  def remaining(self):
    """Returns how much time the record has before being deleted."""
    return self.expires - time.time()

  @property
  def is_expired(self):
    return time.time() > self.expires

  def __eq__(self, other):
    if not isinstance(other, _ExpNode):
      raise TypeError(f'Expected _ExpNode, got {type(other)}')
    return self.expires == other.expires

  def __lt__(self, other):
    if not isinstance(other, _ExpNode):
      raise TypeError(f'Expected _ExpNode, got {type(other)}')
    return self.expires < other.expires

  def __repr__(self):
    classname = self.__class__.__name__
    return f'{classname} {self.key}:({self.remaining})'


def _create_node(key=None, value=None, next=None, prev=None, expires=None):
  """A factory function for easier node creation."""
  if expires is not None:
    return _ExpNode(**locals())
  return _Node(**locals())


class _CacheCleaner(threading.Thread):
  """A daemon thread that is responsible for cleaning up stale items.
  It receives proxied items from a shared queue, picks up the one with
  the shortest life span, and uses a condition variable to wait until the
  item expires. If the item is deleted before it has expired, _CacheCleaner
  is notified and ready to pull out the next item from the queue. If a new item
  is cached, and that new item has a shorter life span than the current item (the one we're
  waiting to become stale), we _CacheCleaner will replace the current item with the new one.

  Attributes:
    _queue: a priority queue through which new items are being pushed through.
    _condition: a condition variable that serves as the waiting mechanism.
      The condition variable is notified ("awoken" from sleep) when an event such
      as adding or deleting an item occurs.
    _cache_ref: a weak reference to the cache object for which this daemon thread is serving.
      It is used for two things: delete a stale item from the cache, and stop the daemon thread
      when the last reference to the cache instance has been garbage collected.
  """

  daemon = True

  def __init__(self, queue, cache, condition, **kwargs):
    self._queue = queue
    self._cache_ref = weakref.ref(cache)
    self._condition = condition
    super(_CacheCleaner, self).__init__(**kwargs)

  def run(self):
    """Contains a loop that continually cleans up stale items
    from the cache. It does not waste CPU resources by waiting
    for an item to expire or by waiting for new items to arrive
    from the queue.
    """
    node_queue = self._queue
    condition = self._condition
    while True:
      cache = self._cache_ref()
      # checking if the cache instance
      # hasn't been garbage collected
      if cache is None:
        break
      # non-blocking wait for a new item
      node = node_queue.get()
      # if the clean up process has been manually stopped
      # kill the thread
      if node is _sentinel:
        break
      with condition:
        while node and (not node.is_expired):
          condition.wait(node.remaining)
          try:
            fast = node_queue.get_nowait()
            if (fast and node) and (fast < node):
              node_queue.put(node)
              node = fast
            elif fast is not None:
              node_queue.put(fast)
          except (queue.Empty, ReferenceError) as error:
            if isinstance(error, ReferenceError):
              node = fast
        node_queue.task_done()
        if cache and node:
          del cache[node.key]
        cache = None


class _CleanManager(object):
  """The middleman between _CacheCleaner and LruCache.
  Responsible for starting the daemon cleaner, passing down
  proxied nodes to it through the shared queue, and notifying the
  cleaner object about different events via condition variable.

  Attributes:
    _queue: priority queue used for communication with the cleaner.
    _condition: condition variable for notifying the cleaner about events.
    _cache_cleaner: a daemon thread, _CacheCleaner, for cleaning up cached items.
    _initialized: a boolean variable indicating whether the cleaner has been started.
  """

  def __init__(self, cache):
    self._queue = queue.PriorityQueue()
    self._condition = threading.Condition()
    self._cache_cleaner = _CacheCleaner(
      self._queue, cache, self._condition
    )
    self._initialized = False

  def add(self, node):
    """Creates a proxy of the node and puts this in the queue.
    As well as wakes up (if needed) the cleaner to consider
    waiting for the new item, potentially with a shorter life span.

    :param node: a new item with that has been cached recently.
    """
    if isinstance(node, _ExpNode):
      if not self._initialized:
        self._initialized = True
        self._cache_cleaner.start()
      node = weakref.proxy(node)
      self._queue.put(node)
      self._notify()

  def _notify(self):
    condition = self._condition
    try:
      with condition:
        condition.notify()
    except RuntimeError:
      pass

  def on_delete(self):
    """Sends a notification to the cleaner object to stop
    waiting for an item that has been deleted.

    :param node: an item that has been deleted.
    """
    self._notify()


class LruCache(MutableMapping):
  """A dictionary-like data structure, supporting LRU caching semantics.
  Additionaly, the cache supports data expiration.

  >>> cache = LruCache(maxsize=128, expires=60)
  >>> cache['foo'] = 'bar'
  >>> cache['foo']
  'bar'
  >>> import time
  >>> time.sleep(60)
  >>> cache['foo']
  Traceback (most recent call last):
    ...
    ...
  KeyError: 'foo'

  >>> cache = LruCache(maxsize=128)
  >>> cache.add('foo', 'bar', expires=10)
  >>> cache['foo']
  'bar'
  >>> time.sleep(10)
  >>> cache['foo']
  Traceback (most recent call last):
    ...
    ...
  KeyError: 'foo'
  """
  def __init__(*args, **kwargs):
    """
    :param maxsize: how many items can the cache keep
      before cleaning up the least used ones
    :param concurrent: a boolean value that indicates whether or not
      the cache will be used in multi-thread environment.
    :param expires: for how long should we retain added items.
    """
    if not args:
      raise ValueError('__init__() needs an argument')
    self, args = args[0], args[1:]
    kwargs = kwargs or {'maxsize':_DEFAULT_CACHE_SIZE}
    if kwargs.setdefault('maxsize', _DEFAULT_CACHE_SIZE) <= 0:
      raise ValueError('maxsize should not be less than or equal to 0')
    try:
      self._maxsize
    except AttributeError:
      self._maxsize = kwargs['maxsize']
      self._hardroot = _Node()
      root = self._root = weakref.proxy(self._hardroot)
      root.next = root.prev = root
      self._mapping = {}
      self._expires = expires = kwargs.get('expires')
      if kwargs.get('concurrent', False):
        self._lock = threading.RLock()
      if expires:
        self._init_cleaner_manager()
    del kwargs['maxsize']
    self.update(*args, **kwargs)

  def _init_cleaner_manager(self):
    self._cleaner_manager = _CleanManager(self)
    if not hasattr(self,'_lock'):
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
    """Adds a key-value pair to the cache.
    :param key: an arbitrary key that is hashable
    :param value: an arbitrary value
    :param expires: indicates in how many seconds
      should the new item expire. If none provided,
      the default duration (if exists) will be used.
    """
    if any([key is None, value is None]):
      raise ValueError('Key and value must not be None')
    # compute the precise time when the item will expire
    expires = self._get_expiration_time(expires)
    if key in self._mapping:
      node = self._mapping[key]
      del self[node.key]
    if len(self._mapping) > self._maxsize:
      del self[self._root.prev.key]
    node = _create_node(key, value, expires=expires)
    self._mapping[key] = node
    self._connect_with_root(node)
    if expires and not hasattr(self, '_cleaner_manager'):
      self._init_cleaner_manager()
    if hasattr(self, '_cleaner_manager'):
      self._cleaner_manager.add(node)

  def _get_expiration_time(self, expires):
    if expires is not None:
      expires = time.time() + expires
    elif self._expires is not None:
      expires = time.time() + self._expires
    return expires

  @lock
  def __delitem__(self, key):
    node = self._mapping.pop(key)
    next, prev = node.next, node.prev
    next.prev = prev
    prev.next = next
    node.next = node.prev = None; del node
    if hasattr(self, '_cleaner_manager'):
      self._cleaner_manager.on_delete()

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
    if isinstance(other, LruCache):
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
    return LruCache(self.items()[::-1])

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
    items = ', '.join((f"{k}: {v}" for k, v in self.items()))
    return f'{{{items}}}'
