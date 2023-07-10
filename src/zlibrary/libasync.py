import asyncio
import re

from bs4 import BeautifulSoup as bsoup
from typing import List, Union
from urllib.parse import quote

from .logger import logger
from .exception import EmptyQueryError, ProxyNotMatchError, NoProfileError, NoDomainError
from .util import GET_request, POST_request, HEAD_request
from .abs import SearchPaginator
from .profile import ZlibProfile
from .const import Extension, Language


ZLIB_DOMAIN = "https://singlelogin.site/"
LOGIN_DOMAIN = "https://singlelogin.site/rpc.php"

ZLIB_TOR_DOMAIN = "http://bookszlibb74ugqojhzhg2a63w5i2atv5bqarulgczawnbmsb6s6qead.onion"
LOGIN_TOR_DOMAIN = "http://loginzlib2vrak5zzpcocc3ouizykn6k5qecgj2tzlnab5wcbqhembyd.onion/rpc.php"


class AsyncZlib:
    semaphore = True
    onion = False

    __semaphore = asyncio.Semaphore(64)
    _jar = None

    cookies = None
    proxy_list = None

    _mirror = ""
    login_domain = None
    domain = None
    profile = None

    @property
    def mirror(self):
        return self._mirror

    @mirror.setter
    def mirror(self, value):
        if not value.startswith('http'):
            value = 'https://' + value
        self._mirror = value

    def __init__(self, onion: bool = False, proxy_list: list = None, disable_semaphore: bool = False):
        if proxy_list:
            if type(proxy_list) is list:
                self.proxy_list = proxy_list
                logger.debug("Set proxy_list: %s", str(proxy_list))
            else:
                raise ProxyNotMatchError

        if onion:
            self.onion = True
            self.login_domain = LOGIN_TOR_DOMAIN
            self.domain = ZLIB_TOR_DOMAIN
            self.mirror = self.domain

            if not proxy_list:
                print("Tor proxy must be set to route through onion domains.\n"
                      "Set up a tor service and use: onion=True, proxy_list=['socks5://127.0.0.1:9050']")
                exit(1)
        else:
            self.login_domain = LOGIN_DOMAIN
            self.domain = ZLIB_DOMAIN

        if disable_semaphore:
            self.semaphore = False

    async def _r(self, url: str):
        if self.semaphore:
            async with self.__semaphore:
                return await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies)
        else:
            return await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies)

    async def login(self, email: str, password: str):
        data = {
            "isModal": True,
            "email": email,
            "password": password,
            "site_mode": "books",
            "action": "login",
            "isSingleLogin": 1,
            "redirectUrl": "",
            "gg_json_mode": 1
        }

        resp, jar = await POST_request(self.login_domain, data, proxy_list=self.proxy_list)
        self._jar = jar

        self.cookies = {}
        for cookie in self._jar:
            self.cookies[cookie.key] = cookie.value
        logger.debug("Set cookies: %s", self.cookies)

        if self.onion:
            url = self.domain + '/?remix_userkey=%s&remix_userid=%s' % (self.cookies['remix_userkey'], self.cookies['remix_userid'])
            resp, jar = await GET_request(url, proxy_list=self.proxy_list, cookies=self.cookies, save_cookies=True)

            self._jar = jar
            for cookie in self._jar:
                self.cookies[cookie.key] = cookie.value
            logger.debug("Set cookies: %s", self.cookies)

            self.mirror = self.domain
            logger.info("Set working mirror: %s" % self.mirror)
        else:
            # make a request to singlelogin to fetch personal user domains
            response = await GET_request(self.domain, proxy_list=self.proxy_list, cookies=self.cookies)
            rexpr = re.compile('const (?:domains|books)(?:List|Domains) = (.*);', flags=re.MULTILINE)
            get_const = rexpr.findall(response)
            if not get_const:
                rexpr = re.compile('const domainsListBooks = (.*);', flags=re.MULTILINE)
                get_const = rexpr.findall(response)

            if get_const:
                group = get_const[0].split('"')
                domains = [dom for dom in group if not dom in [',', '[', ']']]

                logger.info("Available domains: %s" % domains)
                for dom in domains:
                    if not dom.startswith('http'):
                        dom = 'https://' + dom
                    conn = await HEAD_request(dom, proxy_list=self.proxy_list)
                    if conn != 0:
                        self.mirror = dom
                        logger.info("Set working mirror: %s" % self.mirror)
                        break
            if not self.mirror:
                raise NoDomainError

        self.profile = ZlibProfile(self._r, self.cookies, self.mirror, ZLIB_DOMAIN)
        return self.profile

    async def logout(self):
        self._jar = None
        self.cookies = None

    async def search(self, q: str = "", exact: bool = False, from_year: int = None, to_year: int = None,
                     lang: List[Union[Language, str]] = [], extensions: List[Union[Extension, str]] = [], count: int = 10) -> SearchPaginator:
        if not self.profile:
            raise NoProfileError
        if not q:
            raise EmptyQueryError

        payload = "%s/s/%s?" % (self.mirror, quote(q))
        if exact:
            payload += '&e=1'
        if from_year:
            assert str(from_year).isdigit()
            payload += '&yearFrom=%s' % (from_year)
        if to_year:
            assert str(to_year).isdigit()
            payload += '&yearTo=%s' % (to_year)
        if lang:
            assert type(lang) is list
            for l in lang:
                payload += '&languages%5B%5D={}'.format(l if type(l) is str else l.value)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext if type(ext) is str else ext.value)

        paginator = SearchPaginator(url=payload, count=count, request=self._r, mirror=self.mirror)
        await paginator.init()
        return paginator

    async def full_text_search(self, q: str = "", exact: bool = False, phrase: bool = False,
                               words: bool = False, from_year: int = None, to_year: int = None,
                               lang: List[Union[Language, str]] = [], extensions: List[Union[Extension, str]] = [], count: int = 10) -> SearchPaginator:
        if not self.profile:
            raise NoProfileError
        if not q:
            raise EmptyQueryError
        if not phrase and not words:
            raise Exception("You should either specify 'words=True' to match words, or 'phrase=True' to match phrase.")

        payload = "%s/fulltext/%s?" % (self.mirror, quote(q))
        if phrase:
            check = q.split(' ')
            if len(check) < 2:
                raise Exception(("At least 2 words must be provided for phrase search. "
                                 "Use 'words=True' to match a single word."))
            payload += '&type=phrase'
        else:
            payload += '&type=words'

        if exact:
            payload += '&e=1'
        if from_year:
            assert str(from_year).isdigit()
            payload += '&yearFrom=%s' % (from_year)
        if to_year:
            assert str(to_year).isdigit()
            payload += '&yearTo=%s' % (to_year)
        if lang:
            assert type(lang) is list
            for l in lang:
                payload += '&languages%5B%5D={}'.format(l if type(l) is str else l.value)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext if type(ext) is str else ext.value)

        paginator = SearchPaginator(url=payload, count=count, request=self._r, mirror=self.mirror)
        await paginator.init()
        return paginator
