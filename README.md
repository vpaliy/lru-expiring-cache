# LRU Expiring Cache

[![Build Status](https://travis-ci.org/vpaliy/lru-cache.svg?branch=master)](https://travis-ci.org/vpaliy/lru-cache)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![codecov](https://codecov.io/gh/vpaliy/lru-cache/branch/master/graph/badge.svg)](https://codecov.io/gh/vpaliy/lru-cache)

This repository contains a dictionary-like data structure, supporting LRU caching semantics and data expiration mechanism. You can add a new record to the cache and assign an expiration time for that record. Records are not required to have the same "life span": you can mix them up, and it will still work.

### How does it work?
LRU cache uses a daemon thread - AKA cache cleaner - to silently clean up expired items in the background. The daemon thread receives proxied objects from a shared queue, picks up the one with the shortest life span, and uses a condition variable to wait until the record expires.

### Install

`pip install lru-expiring-cache`

or:

```
 $ git clone https://github.com/vpaliy/lru-expiring-cache.git
 $ cd lru-expiring-cache/
```


### Usage

```python
import time
from  lru import LruCache

# every record will expire in 5 seconds unless otherwise specified
cache = LruCache(maxsize=10, expires=5)
cache['foo'] = 'bar'

print(cache['foo']) # prints 'bar'

# sleep for 5 minutes
time.sleep(5)

print(cache['foo']) # KeyError

# adding a new item that expires in 10 seconds
cache.add(key='foo', value='bar', expires=10)

# deleting
del cache['foo']
 ```

To make the LRU cache thread-safe, just pass `concurrent=True` when constructing a new instance:

```python
from lru import LruCache

cache = LruCache(maxsize=10, concurrent=True)
```

Note: LRU cache extends the `MutableMapping` interface from the standard library; therefore it supports all methods inherent to the standard mapping types in Python.

Additionally, you can use cache decorators:

- `lru_cache(maxsize, expires)`
- `lazy_cache(maxsize, expires)`

Both are memoization decorators that support data expiration. The difference is that `lru_cache` uses `LruCache` (obviously) under the hood, and `lazy_cache` uses the native `dict`.

For example, using `lazy_cache` is super easy:

```python
import time
from  lru import lazy_cache

# each new item will expire in 10 seconds
@lazy_cache(maxsize=10, expires=10)
def function(first, second, third):
  # simulate performing a computationaly expensive task
  time.sleep(10)
  return first + second + third

function(10, 10, 10) # sleeps for 10 seconds and returns 30
function(10, 10, 10) # returns 30 instantaneously

time.sleep(10) # wait until expires

function(10, 10, 10) # sleeps for 10 seconds because all cached results have expired

```

Which one to use?

If your function requires the functionality of LRU cache (removing the least recently used records to give room to the new ones), then use `lru_cache`; otherwise if you just need an expiring caching mechaniism, use `lazy_cache`. Note that `lazy_cache` clears the entire cache when the number of records have reached `maxsize`.


## License
```
MIT License

Copyright (c) 2019 Vasyl Paliy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
