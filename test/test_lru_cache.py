import os
import sys
sys.path.insert(0, os.path.abspath('..'))

from lru.lru import LRUCache
import unittest

class LRUCacheTestCase(unittest.TestCase):

  def test_init(self):
    with self.assertRaises(ValueError):
      LRUCache(capacity=0)
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    self.assertEqual(sorted(LRUCache(pairs).items()), pairs)
    self.assertEqual(sorted(LRUCache(dict(pairs)).items()), pairs)
    self.assertEqual(sorted(LRUCache(**dict(pairs)).items()), pairs)
    self.assertEqual(sorted(LRUCache(pairs, e=4, f=5, r=6).items()),
        pairs + [('e', 4), ('f', 5), ('r', 6)])
    cache = LRUCache(pairs)
    cache.__init__([('e', 5), ('t', 6)])
    self.assertEqual(sorted(cache.items()), pairs + [('e', 5), ('t', 6)])

  def test_setitem(self):
    with self.assertRaises(TypeError):
      LRUCache()['a'] = None
    with self.assertRaises(TypeError):
      LRUCache()[None] = 'a'
    with self.assertRaises(TypeError):
      LRUCache()[None] = None
    cache = LRUCache(capacity=10)
    cache['a'] = 1
    cache['b'] = 2
    self.assertEqual(cache.items(), [('b', 2), ('a', 1)])
    cache['a'] = 3
    self.assertEqual(cache.items(), [('a', 3), ('b', 2)])
    cache['b'] = 4
    self.assertEqual(cache.items(), [('b', 4), ('a', 3)])
    cache['c'] = 5
    self.assertEqual(cache.items(), [('c', 5), ('b', 4), ('a', 3)])
    del cache['c']
    cache['c'] = 5
    self.assertEqual(cache.items(), [('c', 5), ('b', 4), ('a', 3)])

  def test_contains(self):
    self.assertFalse('a' in LRUCache())
    self.assertFalse('a' in LRUCache([('b', 2), ('c', 3), ('d', 4)]))
    self.assertTrue('b' in LRUCache([('b', 2), ('c', 3), ('d', 4)]))
    self.assertTrue('b' not in LRUCache())
    self.assertTrue('b' not in LRUCache([('c', 3), ('d', 4)]))
    cache = LRUCache([('b', 2), ('c', 3), ('d', 4)])
    self.assertTrue('a' not in cache)
    cache['a'] = 3
    self.assertTrue('a' in cache)

  def test_getitem(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    with self.assertRaises(KeyError):
      LRUCache()['key']
    with self.assertRaises(KeyError):
      cache['key']
    for key, value in pairs:
      self.assertEqual(value, cache[key])

  def test_delitem(self):
    with self.assertRaises(KeyError):
      del LRUCache()['key']
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    with self.assertRaises(KeyError):
      del cache['key']
    for index, (key, value) in enumerate(pairs):
      del cache[key]
      self.assertEqual(cache.items(), pairs[index+1:][::-1])
    # start deleting from the tail
    cache.update(pairs)
    for index, (key, value) in enumerate(pairs[::-1]):
      del cache[key]
      index = len(pairs) - index - 1
      self.assertEqual(cache.items(), pairs[:index][::-1])

  def test_len(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    self.assertEqual(len(pairs), len(cache))
    del cache['a']
    self.assertEqual(len(pairs) - 1, len(cache))
    cache.clear()
    self.assertEqual(len(cache), 0)

  def test_clear(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    self.assertEqual(len(cache), len(pairs))
    cache.clear()
    self.assertEqual(len(cache), 0)
    cache.clear()
    self.assertEqual(len(cache), 0)
    cache.update(pairs)
    self.assertEqual(len(cache), len(pairs))
    cache.clear()
    self.assertEqual(len(cache), 0)

  def test_iter(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    values = [value for key, value in pairs][::-1]
    cache = LRUCache(pairs)
    self.assertEqual(list(iter(cache)), values)

  def test_copy(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    self.assertEqual(cache.copy().items(), cache.items())
    self.assertEqual(cache.copy().keys(), cache.keys())
    self.assertEqual(LRUCache().items(), LRUCache().copy().items())
    self.assertEqual(LRUCache().keys(), LRUCache().copy().keys())

  def test_repr(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    self.assertEqual(repr(cache),'\n'.join(['%s:%s' % (key, value)
        for key, value in pairs[::-1]]))
    self.assertEqual(repr(LRUCache()), str())

  def test_eq(self):
    pairs = [('a', 1), ('b', 2), ('c', 3), ('d', 4)]
    cache = LRUCache(pairs)
    self.assertTrue(cache == cache)
    self.assertTrue(LRUCache() == LRUCache())
    self.assertTrue(LRUCache(pairs) == LRUCache(pairs))
    self.assertFalse(LRUCache() == list())
    self.assertFalse(LRUCache(pairs) == LRUCache(pairs[1:]))
    self.assertFalse(LRUCache(pairs) == LRUCache(pairs[::-1]))

def main():
  unittest.main()

if __name__ == '__main__':
  main()
