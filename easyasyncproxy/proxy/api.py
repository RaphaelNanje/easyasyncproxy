import asyncio
import functools
from typing import Iterable, Union, TYPE_CHECKING, Optional

import requests
from requests import Response, Session
from yarl import URL

from easyasyncproxy.proxy import config
from easyasyncproxy.proxy.exceptions import BadProxyError, bad_proxy_exceptions

if TYPE_CHECKING:
    from easyasyncproxy.proxy import Proxy


class ProxyApi:

    def __init__(self, links=None, proxies: Iterable[str] = None,
                 timeout=5, headers: dict = None, clear_on_fail=False,
                 free_sources=True, threads_per_proxy=None,
                 rotating=False) -> None:
        """

        Args:
            links:
            proxies:
            timeout:
            headers:
            clear_on_fail: Whether to clear proxies from session when a
                BadProxy is raised (default: True)
            rotating: When using rotating proxies. This enables automatically 
                releasing proxies after fail/use
        """
        self.headers = headers or config.HEADERS
        self.timeout = timeout
        self.rotating = rotating
        self.clear_on_fail = clear_on_fail

        self._loop = asyncio.get_event_loop()

        from easyasyncproxy.proxy import AsyncProxyManager
        self.manager = AsyncProxyManager(from_file=proxies, links=links or [],
                                         free_sources=free_sources,
                                         threads_per_proxy=threads_per_proxy,
                                         lifo=not rotating)
        self.manager.refresh_proxies()

    async def get(self, url: Union[str, URL], params: dict = None, loop=None,
                  headers: dict = None, timeout: int = None, **kwargs):
        proxy = await self.manager.acquire()
        loop = loop or self._loop
        future = loop.run_in_executor(None, functools.partial(
            requests.get,
            url,
            params=params or {},
            timeout=timeout or self.timeout,
            headers=headers or self.headers,
            proxies=proxy.as_dict,
            **kwargs
        ))
        try:
            response = await future
        except bad_proxy_exceptions:
            raise BadProxyError(proxy)
        finally:
            if self.rotating:
                self.manager.release(proxy)

        return ProxyResponse(proxy, response)

    async def post(self, url: Union[str, URL], data: dict = None, loop=None,
                   headers: dict = None, timeout: int = None, **kwargs):
        proxy = await self.manager.acquire()
        loop = loop or self._loop
        future = loop.run_in_executor(None, functools.partial(
            requests.post,
            url,
            data=data or {},
            timeout=timeout or self.timeout,
            headers=headers or self.headers,
            proxies=proxy.as_dict,
            **kwargs
        ))
        try:
            response = await future
        except bad_proxy_exceptions:
            raise BadProxyError(proxy)
        finally:
            if self.rotating:
                self.manager.release(proxy)
        return ProxyResponse(proxy, response)

    async def session_post(self, session: Session, url: Union[str, URL],
                           data: dict = None, loop=None, timeout: int = None,
                           **kwargs):
        proxy = self.get_proxy_from_session(session)
        if not any(session.proxies):
            proxy = await self.manager.acquire()
            session.proxies.update(proxy.as_dict)
        loop = loop or self._loop
        future = loop.run_in_executor(None, functools.partial(
            session.post,
            url,
            data=data,
            timeout=timeout or self.timeout,
            **kwargs
        ))
        try:
            response = await future
        except bad_proxy_exceptions as e:
            if self.clear_on_fail:
                session.proxies.clear()
            raise BadProxyError(proxy, str(e))
        finally:
            if self.rotating:
                self.manager.release(proxy)
        return ProxyResponse(proxy, response)

    async def session_get(self, session: Session, url: Union[str, URL],
                          params: dict = None, loop=None, timeout: int = None,
                          **kwargs):
        loop = loop or self._loop
        proxy = self.get_proxy_from_session(session)
        if not proxy:
            proxy = await self.manager.acquire()
            session.proxies.update(proxy.as_dict)
        future = loop.run_in_executor(None, functools.partial(
            session.get,
            url,
            params=params,
            timeout=timeout or self.timeout,
            **kwargs
        ))
        try:
            response = await future
        except bad_proxy_exceptions as e:
            if self.clear_on_fail:
                session.proxies.clear()

            raise BadProxyError(proxy, str(e))
        finally:
            if self.rotating:
                self.manager.release(proxy)
        return ProxyResponse(proxy, response)

    def release(self, proxy: 'Proxy'):
        self.manager.release(proxy)

    @staticmethod
    def get_proxy_from_session(session: Session) -> Optional['Proxy']:
        # noinspection PyUnresolvedReferences
        proxy_dict = session.proxies.copy()
        if not any(proxy_dict):
            return None
        protocol, link = proxy_dict.popitem()
        from easyasyncproxy.proxy import Proxy
        return Proxy.from_url(link)


class ProxyResponse(Response):

    def __init__(self, proxy: 'Proxy', response: Response) -> None:
        super().__init__()
        self.__dict__.update(vars(response))
        self.proxy = proxy
