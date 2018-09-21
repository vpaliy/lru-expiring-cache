from weakref import proxy
try:
  from collections.abc import MutableMapping
except ImportError:
  from collections import MutableMapping

class Node(object):
  __slots__ = ('next', 'prev', 'key', 'value', '__weakref__')

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
      root = self._root = proxy(self._hardroot)
      root.next = root.prev = root
      self._mapping = {}
    del kwargs['capacity']
    self.update(*args, **kwargs)

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

  def __getitem__(self, key):
    node = self._mapping[key]
    self._bump_up(node)
    return node.value

  def __setitem__(self, key, value):
    if any([key is None, value is None]):
      raise TypeError
    if key in self._mapping:
      node = self._mapping[key]
      node.value = value
      self._bump_up(node)
      return
    if len(self._mapping) > self._capacity:
      del self[self._root.prev.key]
    node = Node()
    node.key, node.value = key, value
    self._mapping[key] = node
    self._connect_with_root(node)

  def __delitem__(self, key):
    node = self._mapping.pop(key)
    next, prev = node.next, node.prev
    next.prev = prev
    prev.next = next
    node.next = node.prev = None

  def __iter__(self):
    return iter(self.values())

  def __contains__(self, key):
    return key in self._mapping

  def __len__(self):
    return len(self._mapping)

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

  def _iterator(self):
    root = self._root
    node = root.next
    while node is not root:
      next = node.next
      yield node
      node = next

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
    return '\n'.join(('%s:%s' % (k, v)
        for k, v in self.items()))
