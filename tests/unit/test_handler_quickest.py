# -*- coding: utf-8 -*-
import pytest
from greendns.handler_quickest import QuickestHandler
from greendns.handler_quickest import QuickestRequest


@pytest.fixture
def quickest():
    h = QuickestHandler()
    return h


def test_get_request(quickest):
    r = quickest.get_request()
    assert isinstance(r, QuickestRequest)


def test_on_upstream_response(quickest):
    r = quickest.get_request()
    r.server_resps[("223.5.5.5", 53)] = "123456"
    resp = quickest.on_upstream_response(r)
    assert resp == "123456"
