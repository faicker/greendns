# -*- coding: utf-8 -*-
import struct
import socket


class LocalNet(object):
    def __init__(self, localroutes, blacklists, using_rfc1918):
        self.local_subs = []
        self.blackips = set()

        for sub in localroutes:
            (l, h) = self.convert(sub)
            if l and h:
                self.local_subs.append((l, h))
        for ip in blacklists:
            try:
                self.blackips.add(struct.unpack('>I', socket.inet_aton(ip))[0])
            except socket.error:
                continue
        if using_rfc1918:
            self.local_subs.append(self.convert("192.168.0.0/16"))
            self.local_subs.append(self.convert("10.0.0.0/8"))
            self.local_subs.append(self.convert("172.16.0.0/12"))
        self.local_subs.sort()

    def convert(self, net):
        parts = net.split('/')
        if len(parts) != 2:
            return (-1, -1)
        ip_s, mask_s = parts[0], parts[1]
        if ip_s and mask_s:
            try:
                ip = struct.unpack('>I', socket.inet_aton(ip_s))[0]
            except socket.error:
                return (-1, -1)
            mask = int(mask_s)
            if mask < 0 or mask > 32:
                return (-1, -1)
            hex_mask = 0xffffffff - (1 << (32 - mask)) + 1
            lowest = ip & hex_mask
            highest = lowest + (1 << (32 - mask)) - 1
            return (lowest, highest)

    def is_in_blacklist(self, str_ip):
        try:
            ip = struct.unpack('>I', socket.inet_aton(str_ip))[0]
        except socket.error:
            return False
        if ip in self.blackips:
            return True
        else:
            return False

    def is_in_local(self, str_ip):
        '''binary search'''
        try:
            ip = struct.unpack('>I', socket.inet_aton(str_ip))[0]
        except socket.error:
            return False
        i = 0
        j = len(self.local_subs) - 1
        while (i <= j):
            k = (i + j) // 2
            if ip > self.local_subs[k][1]:
                i = k + 1
            elif ip < self.local_subs[k][0]:
                j = k - 1
            else:
                return True
        return False
