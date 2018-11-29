# -*- coding: utf-8 -*-
import pytest
from greendns.handler_quickest import QuickestHandler
from greendns.handler_quickest import QuickestSession


@pytest.fixture
def quickest():
    h = QuickestHandler()
    return h


def test_get_session(quickest):
    s = quickest.get_session()
    assert isinstance(s, QuickestSession)


def test_on_upstream_response(quickest):
    s = quickest.get_session()
    addr = ("223.5.5.5", 53)
    s.server_resps[addr] = "123456"
    resp = quickest.on_upstream_response(s, addr)
    assert resp == "123456"
