import asyncio
import aiohttp
import traceback
import logging
import sys

from bs4 import BeautifulSoup as bsoup
from typing import Callable
from urllib.parse import quote

from .logger import logger
from .exception import LoopError, EmptyQueryError, NoDomainError, ParseError


ZLIB_DOMAIN = "https://z-lib.org/"


async def request(url):
    head = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    }
    timeout = aiohttp.ClientTimeout(
        total=90,
        connect=0,
        sock_connect=0,
        sock_read=0
    )
    try:
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            logger.info("GET %s" % url)
            async with sess.get(url) as resp:
                return await resp.text()
    except asyncio.exceptions.CancelledError:
        raise LoopError("Asyncio loop had been closed before request could finish.")
    except Exception as e:
        logger.critical(traceback.format_exc())
        raise Exception(e)


class ListItem(dict):
    parsed = None

    def __init__(self, request, domain):
        super().__init__()
        self.__r = request
        self.domain = domain

    async def fetch(self): 
        page = await self.__r(self['url'])
        soup = bsoup(page, features='lxml')

        wrap = soup.find('div', { 'class': 'row cardBooks' })
        if not wrap:
            raise ParseError("Failed to parse %s" % self['url'])

        parsed = {}
        parsed['url'] = self['url']
        parsed['name'] = self['name']

        anchor = wrap.find('a', { 'class': 'details-book-cover' })
        if anchor:
            parsed['cover'] = anchor.get('href')

        desc = wrap.find('div', { 'id': 'bookDescriptionBox' })
        parsed['description'] = desc.text.strip()

        details = wrap.find('div', { 'class': 'bookDetailsBox' })

        properties = [
                'year',
                'edition',
                'publisher',
                'language',
                'isbn 10',
                'isbn 13',
        ]
        for prop in properties:
            x = details.find('div', { 'class': 'property_' + prop })
            if x:
                x = x.find('div', { 'class': 'property_value' })
                parsed[prop] = x.text.strip()

        cat = details.find('div', { 'class': 'property_categories' })
        if cat:
            cat = cat.find('div', { 'class': 'property_value' })
            link = cat.find('a')
            parsed['categories'] = cat.text.strip()
            parsed['categories_url'] = '%s%s' % (self.domain, link.get('href'))

        file = details.find('div', { 'class': 'property__file'})
        file = file.text.strip().split(',')
        parsed['extension'] = file[0].split('\n')[1]
        parsed['size'] = file[1]
        
        rating = wrap.find('div', { 'class': 'book-rating'})
        parsed['rating'] = ''.join(filter(lambda x: bool(x), rating.text.replace('\n', '').split(' ')))

        det = soup.find('div', { 'class': 'book-details-button' })
        dl_link = det.find('a', { 'class': 'dlButton' })
        if not dl_link:
            raise ParseError("Could not parse the download link.")
        
        parsed['download_url'] = '%s%s' % (self.domain, dl_link.get('href'))
        self.parsed = parsed
        return parsed


class ResultPaginator:
    __url = ""
    __pos = 0
    __r = None

    domain = ""
    page = 1
    total = 0
    count = 10

    result = []

    storage = {
        1: []
    }

    def __init__(self, url: str, count: int, request: Callable, domain: str):
        self.count = count
        self.__url = url
        self.__r = request
        self.domain = domain

    def parse_page(self, page):
        soup = bsoup(page, features='lxml')
        box = soup.find('div', { 'id': 'searchResultBox' })
        if not box:
            raise ParseError("Could not parse book list.")

        check_notfound = soup.find('div', { 'class': 'notFound' })
        if check_notfound:
            logger.debug("Nothing found.")
            self.storage = {
                1: []
            }
            return

        book_list = box.findAll('div', { 'class': 'resItemBox' })
        if not book_list:
            raise ParseError("Could not find the book list.")

        self.storage[self.page] = []

        for idx, book in enumerate(book_list, start=1):
            js = ListItem(self.__r, self.domain)

            book = book.find('table', { 'class': 'resItemTable' })
            cover = book.find('div', { 'class': 'itemCoverWrapper' })
            if not cover:
                logger.debug("Failure to parse %d-th book at url %s" % (idx, self.__url))
                continue

            js['id'] = cover.get('data-book_id')
            js['isbn'] = cover.get('data-isbn')

            book_url = cover.find('a')
            if book_url:
                js['url'] = '%s%s' % (self.domain, book_url.get('href'))
            img = cover.find('img')
            if img:
                js['cover'] = img.get('data-src')

            data_table = book.find('table')
            name = data_table.find('h3', { 'itemprop': 'name' })
            if not name:
                raise ParseError("Could not parse %d-th book at url %s" % (idx, self.__url))
            js['name'] = name.text.strip()

            publisher = data_table.find('a', { 'title': 'Publisher' })
            if publisher:
                js['publisher'] = publisher.text.strip()
                js['publisher_url'] = '%s%s' % (self.domain, publisher.get('href'))

            authors = data_table.find('div', { 'class': 'authors' })
            anchors = authors.findAll('a')
            if anchors:
                js['authors'] = []
            for adx, an in enumerate(anchors, start=1):
                js['authors'].append({
                    'author': an.text.strip(),
                    'author_url': '%s%s' % (self.domain, an.get('href'))
                })

            year = data_table.find('div', { 'class': 'property_year' })
            if year:
                year = year.find('div', { 'class': 'property_value' })
                js['year'] = year.text.strip()

            lang = data_table.find('div', { 'class': 'property_language' })
            if lang:
                lang = lang.find('div', { 'class': 'property_value' })
                js['language'] = lang.text.strip()

            file = data_table.find('div', { 'class': 'property__file'})
            file = file.text.strip().split(',')
            js['extension'] = file[0].split('\n')[1]
            js['size'] = file[1]

            rating = data_table.find('div', { 'class': 'property_rating'})
            js['rating'] = ''.join(filter(lambda x: bool(x), rating.text.replace('\n', '').split(' ')))
            
            self.storage[self.page].append(js)
        
        scripts = soup.findAll('script')
        for scr in scripts:
            txt = scr.text
            if 'var pagerOptions' in txt:
                pos = txt.find('pagesTotal: ')
                fix = txt[pos + len('pagesTotal: ') :]
                count = fix.split(',')[0]
                self.total = int(count)

    async def init(self):
        page = await self.fetch_page()
        self.parse_page(page)

    async def fetch_page(self):
        return await self.__r('%s&page=%d' % (self.__url, self.page))

    async def next(self):
        if self.__pos >= len(self.storage[self.page]):
            await self.next_page()

        self.result = self.storage[self.page][self.__pos : self.__pos + self.count]
        self.__pos += self.count
        return self.result

    async def prev(self):
        self.__pos -= self.count
        if self.__pos < 1:
            await self.prev_page()

        subtract = self.__pos - self.count
        if subtract < 0:
            subtract = 0
        if self.__pos <= 0:
            self.__pos = self.count

        self.result = self.storage[self.page][subtract : self.__pos]
        return self.result

    async def next_page(self):
        if self.page < self.total:
            self.page += 1
            self.__pos = 0
        else:
            self.__pos = len(self.storage[self.page]) - self.count - 1

        if not self.storage.get(self.page):
            page = await self.fetch_page()
            self.parse_page(page)

    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
        else:
            self.__pos = 0
            return

        if not self.storage.get(self.page):
            page = await self.fetch_page()
            self.parse_page(page)

        self.__pos = len(self.storage[self.page])


class AsyncZlib:
    domain = ""
    semaphore = True
    __semaphore = asyncio.Semaphore(64)

    async def init(self, no_semaphore=False):
        page = await self._r(ZLIB_DOMAIN)
        soup = bsoup(page, features='lxml')
        check = soup.find('div', { 'class': 'domain-check-error hidden' })
        if not check:
            raise NoDomainError

        dom = soup.find('div', { 'class': 'domain-check-success' })
        if not dom:
            raise NoDomainError

        self.domain = "https://%s" % dom.text.strip()
        logger.debug("Set working domain: %s" % self.domain)

        if no_semaphore:
            self.semaphore = False

    async def _r(self, url: str):
        if self.semaphore:
            async with self.__semaphore:
                return await request(url)
        else:
            return await request(url)

    async def search(self, q="", precise=False, from_year=None, to_year=None,
                     lang=[], extensions=[], count=10) -> ResultPaginator:
        if not q:
            raise EmptyQueryError

        payload = "%s/s/%s?" % (self.domain, quote(q))
        if precise:
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
                payload += '&languages%5B%5D={}'.format(l)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext)

        paginator = ResultPaginator(url=payload, count=count, request=self._r, domain=self.domain)        
        await paginator.init()
        return paginator

    async def full_text_search(self, q="", precise=False, phrase=True, words=False,
                               from_year=None, to_year=None, lang=[], extensions=[], count=10) -> ResultPaginator:
        if not q:
            raise EmptyQueryError

        payload = "%s/s/%s?" % (self.domain, quote(q))
        if phrase:
            payload += '&type=phrase'
        else:
            payload += '&type=words'

        if precise:
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
                payload += '&languages%5B%5D={}'.format(l)
        if extensions:
            assert type(extensions) is list
            for ext in extensions:
                payload += '&extensions%5B%5D={}'.format(ext)

        paginator = ResultPaginator(url=payload, count=count, request=self._r, domain=self.domain)        
        await paginator.init()
        return paginator

