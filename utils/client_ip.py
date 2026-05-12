#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Реальный IP клиента за reverse proxy (nginx)."""


def get_client_ip(req) -> str:
    """
    Берёт первый адрес из X-Forwarded-For, иначе X-Real-IP, иначе remote_addr.
    Не доверяем произвольным заголовкам без прокси — в проде nginx подставляет X-Forwarded-For.
    """
    xff = (req.headers.get('X-Forwarded-For') or '').strip()
    if xff:
        first = xff.split(',')[0].strip()
        if first:
            return first[:45]
    xr = (req.headers.get('X-Real-IP') or '').strip()
    if xr:
        return xr[:45]
    return (req.remote_addr or '')[:45]
