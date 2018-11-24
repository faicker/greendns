# -*- coding: utf-8 -*-
import time
import pytest
from greendns.cache import Cache


@pytest.fixture
def cache():
    c = Cache()
    c.add(1, "11", 1)
    c.add(2, "22", 2)
    c.add(3, "33", 3)
    return c


def test_iteritems(cache):
    for k, (v, expire_ts) in cache.iteritems():
        if k == 2:
            assert v == "22"


def test_add(cache):
    assert len(cache) == 3


def test_remove(cache):
    old_len = len(cache)
    cache.remove(1)
    cache.remove(2)
    cache.remove(3)
    assert len(cache) == old_len - 3
    cache.remove(4)
    assert len(cache) == 0


def test_find(cache):
    old_len = len(cache)
    v = cache.find(1)
    assert v == "11"
    v = cache.find(2)
    assert v == "22"
    v = cache.find(3)
    assert v == "33"
    assert len(cache) == old_len


def test_validate(cache):
    old_len = len(cache)
    cache.validate()
    assert len(cache) == old_len


def test_cache(cache):
    old_len = len(cache)
    time.sleep(1.0)
    cache.validate()
    assert len(cache) == old_len - 1
    assert cache.find(1) is None

    time.sleep(2.0)
    assert cache.find(2) is None
    assert len(cache) == old_len - 2
    cache.validate()
    assert len(cache) == 0
