# -*- coding: utf-8 -*-
from greendns.localnet import LocalNet


def test_convert():
    cnet = LocalNet([], [], False)
    (l, h) = cnet.convert("192.168.0.0/16")
    assert l == 0XC0A80000
    assert h == 0XC0A8FFFF
    (l, h) = cnet.convert("172.16.8.0/24")
    assert l == 0XAC100800
    assert h == 0XAC1008FF
    (l, h) = cnet.convert("255.255.255.255/32")
    assert l == 0XFFFFFFFF
    assert h == 0XFFFFFFFF
    (l, h) = cnet.convert("0.0.0.0/0")
    assert l == 0
    assert h == 0XFFFFFFFF
    (l, h) = cnet.convert("172.16.8.0/34")
    assert l == -1
    assert h == -1
    (l, h) = cnet.convert("256.16.8.0/3")
    assert l == -1
    assert h == -1
    (l, h) = cnet.convert("256.16.8.1")
    assert l == -1
    assert h == -1


def test_is_in_blacklist():
    blacklist = ["1.2.3.4", "2.3.4.5", "110.20.3.43",
                 "23.97.5.142", "8.55.32.143", "300.2.2.2"]
    cnet = LocalNet([], blacklist, False)
    for ip in blacklist:
        if ip == "300.2.2.2":
            assert not cnet.is_in_blacklist(ip)
        else:
            assert cnet.is_in_blacklist(ip)
    for ip in ["1.2.3.5", "1.2.3.3", "2.3.4.4", "22.3.4.5",
               "254.32.4.5", "110.20.3.3", "330.2.2.3"]:
        assert not cnet.is_in_blacklist(ip)


def test_is_in_local():
    localroutes = ["1.1.8.0/24", "223.20.0.0/15",
                 "210.28.0.0/14", "210.15.32.0/19", "163.0.0.0/16"]
    cnet = LocalNet(localroutes, [], False)
    cnet_rfc1918 = LocalNet(localroutes, [], True)
    for ip in ["1.1.8.0", "1.1.8.255", "223.20.0.23", "223.20.0.1",
               "223.21.255.255", "210.28.0.0", "210.15.32.25", "163.0.2.3"]:
        assert cnet.is_in_local(ip)
    for ip in ["1.1.7.255", "1.1.9.0", "23.0.20.223", "163.2.0.3",
               "254.3.4.5", "8.8.8.8", "257.1223.3.3"]:
        assert not cnet.is_in_local(ip)
    assert cnet_rfc1918.is_in_local("192.168.2.3")
    assert cnet_rfc1918.is_in_local("10.2.3.4")
    assert cnet_rfc1918.is_in_local("172.23.2.3")
