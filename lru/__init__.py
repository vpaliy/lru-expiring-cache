
__version__ = '1.0'
__all___ = ['LruCache', 'lazy_cache', 'lru_cache']

from lru.cache import LruCache
from lru.decorators import lazy_cache, lru_cache
