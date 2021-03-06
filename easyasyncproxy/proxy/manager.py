import logging
import random
import re
from asyncio import LifoQueue, Queue
from typing import List, Tuple, Iterable
from urllib.parse import urlsplit

import requests

from . import config
from .proxy import Proxy

proxy_pattern = re.compile(r'([\w\-]+\.[\w.-]+):(\d+)')
url_pattern = re.compile(r'([\w\-]+\.[\w.-]+)')

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def get_proxies(url) -> List[Tuple[str, str]]:
    """
    :return: List of proxy&port tuples.
    """
    headers = config.HEADERS

    # noinspection PyBroadException
    try:
        response = _get_proxy_response(headers, url)
    except Exception:
        return []

    text = response.text
    find_all = format_proxies(text)
    if not find_all:
        logging.getLogger('get-proxies').debug(
            'Unable to retrieve proxies from %s.\nResponse: %s', url,
            response.text)
        return []
    return find_all


class AsyncProxyManager:
    proxies = set()
    bad_proxies = set()
    proxies_from_file = set()

    def __init__(self, links: Iterable[Tuple[str, str]] = None,
                 max_proxies=10_000, from_file=None, free_sources=True,
                 threads_per_proxy=None, lifo=True):
        self.max_proxies = max_proxies
        self.threads_per_proxy = threads_per_proxy or 1
        links = links or []
        self.sources = config.sources if free_sources else {}
        for link in links:
            self.add_source(link)
        if from_file:
            self.proxies_from_file = format_proxies('\n'.join(from_file))

        self.queue = LifoQueue() if lifo else Queue()

    def refresh_proxies(self):
        logger.info('refreshing proxies...')
        if self.proxies_from_file:
            self.proxies.update(self.proxies_from_file[:self.max_proxies])
        for link in self.sources.values():
            self.proxies.update(get_proxies(link)[:self.max_proxies])

        logger.info('retrieved %s proxies', len(self.proxies))
        proxies = list(self.proxies)
        random.shuffle(proxies)
        for proxy in proxies:
            for i in range(self.threads_per_proxy):
                self.queue.put_nowait(Proxy(*proxy))

    async def acquire(self) -> Proxy:
        if self.queue.qsize() == 0:
            self.refresh_proxies()
        logger.debug('grabbing proxy from queue...')
        proxy = await self.queue.get()
        logger.debug('grabbed proxy from queue.')

        return proxy

    def release(self, proxy):
        self.queue.put_nowait(proxy)
        logger.debug('proxy added back to queue.')

    logger.debug('proxy added back to queue.')

    @property
    def proxies_left(self):
        return self.proxies

    def add_source(self, link):
        url_split = urlsplit(link)
        self.sources[url_split.hostname] = link


def format_proxies(text):
    text = url_pattern.sub(r'http://\1', text)
    find_all = proxy_pattern.findall(text)
    return find_all


def _get_proxy_response(headers, url):
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.ReadTimeout:
        logging.getLogger('get-proxies').debug(
            'Timed out while retrieving proxies from %s.', url)
        raise
    if not response.status_code == 200:
        logging.getLogger('get-proxies').error(
            'Received non200 while retrieving proxies from %s', url)
        raise
    return response
