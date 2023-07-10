from typing import Callable
from bs4 import BeautifulSoup as bsoup
from urllib.parse import quote

from .exception import ParseError
from .logger import logger

import json


DLNOTFOUND = 'Downloads not found'
LISTNOTFOUND = 'On your request nothing has been found'


class SearchPaginator:
    __url = ""
    __pos = 0
    __r = None

    mirror = ""
    page = 1
    total = 0
    count = 10

    result = []

    storage = {
        1: []
    }

    def __init__(self, url: str, count: int, request: Callable, mirror: str):
        if count > 50:
            count = 50
        if count <= 0:
            count = 1
        self.count = count
        self.__url = url
        self.__r = request
        self.mirror = mirror

    def __repr__(self):
        fmt = '<Paginator [%s], count %d, len(result): %d, pages in storage: %d>'
        return  fmt % (self.__url, self.count, len(self.result), len(self.storage.keys()))

    def parse_page(self, page):
        soup = bsoup(page, features='lxml')
        box = soup.find('div', { 'id': 'searchResultBox' })
        if not box:
            raise ParseError("Could not parse book list.")

        check_notfound = soup.find('div', { 'class': 'notFound' })
        if check_notfound:
            logger.debug("Nothing found.")
            self.storage[self.page] = []
            self.result = []
            return

        book_list = box.findAll('div', { 'class': 'resItemBox' })
        if not book_list:
            raise ParseError("Could not find the book list.")

        self.storage[self.page] = []

        for idx, book in enumerate(book_list, start=1):
            js = BookItem(self.__r, self.mirror)

            book = book.find('table', { 'class': 'resItemTable' })
            cover = book.find('div', { 'class': 'itemCoverWrapper' })
            if not cover:
                logger.debug("Failure to parse %d-th book at url %s" % (idx, self.__url))
                continue

            js['id'] = cover.get('data-book_id')
            js['isbn'] = cover.get('data-isbn')

            book_url = cover.find('a')
            if book_url:
                js['url'] = '%s%s' % (self.mirror, book_url.get('href'))
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
                js['publisher_url'] = '%s%s' % (self.mirror, publisher.get('href'))

            authors = data_table.find('div', { 'class': 'authors' })
            anchors = authors.findAll('a')
            if anchors:
                js['authors'] = []
            for adx, an in enumerate(anchors, start=1):
                js['authors'].append({
                    'author': an.text.strip(),
                    'author_url': '%s%s' % (self.mirror, quote(an.get('href')))
                })

            year = data_table.find('div', { 'class': 'property_year' })
            if year:
                year = year.find('div', { 'class': 'property_value' })
                if year:
                    js['year'] = year.text.strip()

            lang = data_table.find('div', { 'class': 'property_language' })
            if lang:
                lang = lang.find('div', { 'class': 'property_value' })
                if lang:
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
            self.__pos -= self.count
            if self.__pos < 0:
                self.__pos = 0

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


class BooklistPaginator:
    __url = ""
    __pos = 0
    __r = None

    mirror = ""
    page = 1
    total = 1
    count = 10

    result = []

    storage = {
        1: []
    }

    def __init__(self, url: str, count: int, request: Callable, mirror: str):
        self.count = count
        self.__url = url
        self.__r = request
        self.mirror = mirror

    def __repr__(self):
        fmt = '<Booklist paginator [%s], count %d, len(result): %d, pages in storage: %d>'
        return  fmt % (self.__url, self.count, len(self.result), len(self.storage.keys()))

    def parse_page(self, page):
        soup = bsoup(page, features='lxml')

        check_notfound = soup.find('div', { 'class': 'cBox1' })
        if check_notfound and LISTNOTFOUND in check_notfound.text.strip():
            logger.debug("Nothing found.")
            self.storage[self.page] = []
            self.result = []
            return

        book_list = soup.findAll('div', { 'class': 'readlist-item' })
        if not book_list:
            raise ParseError("Could not find the booklists.")

        self.storage[self.page] = []

        for idx, book in enumerate(book_list, start=1):
            js = BooklistItemPaginator(self.__r, self.mirror, self.count)

            name = book.find('div', { 'class': 'title' })
            if not name:
                raise ParseError("Could not parse %d-th booklist at url %s" % (idx, self.__url))
            js['name'] = name.text.strip()

            book_url = name.find('a')
            if book_url:
                js['url'] = '%s%s' % (self.mirror, book_url.get('href'))

            info_wrap = book.find('div', { 'class': 'readlist-info' })

            author = info_wrap.find('div', { 'class': 'author' })
            if author:
                js['author'] = author.text.strip()
            date = info_wrap.find('div', { 'class': 'date' })
            if date:
                js['date'] = date.text.strip()
            count = info_wrap.find('div', { 'class': 'books-count' })
            if count:
                js['count'] = count.text.strip()
            views = info_wrap.find('div', { 'class': 'views-count' })
            if views:
                js['views'] = views.text.strip()
            
            js['books_lazy'] = []
            carousel = book.find('div', { 'class': 'zlibrary-carousel' })
            if not carousel:
                self.storage[self.page].append(js)
                continue
            covers = carousel.findAll('div', { 'class': 'carousel-cell-inner' })

            for adx, cover in enumerate(covers):
                res = BookItem(self.__r, self.mirror)
                anchor = cover.find('a')
                if anchor:
                    res['url'] = '%s%s' % (self.mirror, anchor.get('href'))
                res['name'] = ""

                check = cover.find('div', { 'class': 'checkBookDownloaded' })
                res['id'] = check['data-book_id']

                img = check.find('img')
                res['cover'] = img.get('data-flickity-lazyload')
                if not res['cover']:
                    res['cover'] = img.get('data-src')

                js['books_lazy'].append(res)

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
        return self

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
            self.__pos -= self.count
            if self.__pos < 0:
                self.__pos = 0

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


class DownloadsPaginator:
    __url = ""
    __r = None
    page = 1
    mirror = ""

    result = []

    storage = {
        1: []
    }

    def __init__(self, url: str, page: int, request: Callable, mirror: str):
        self.__url = url
        self.__r = request
        self.mirror = mirror
        self.page = page

    def __repr__(self):
        return '<Downloads paginator [%s]>' % self.__url

    def parse_page(self, page):
        soup = bsoup(page, features='lxml')
        box = soup.find('div', { 'class': 'dstats-content' })
        if not box:
            raise ParseError("Could not parse downloads list.")

        check_notfound = box.find('p')
        if check_notfound and DLNOTFOUND in check_notfound.text.strip():
            logger.debug("This page is empty.")
            self.storage[self.page] = []
            self.result = []
            return

        book_list = box.findAll('tr', { 'class': 'dstats-row' })
        if not book_list:
            raise ParseError("Could not find the book list.")

        self.storage[self.page] = []

        for _, book in enumerate(book_list, start=1):
            js = BookItem(self.__r, self.mirror)

            title = book.find('div', { 'class': 'book-title' })
            date = book.find('td', { 'class': 'lg-w-120' })

            js['name'] = title.text.strip()
            js['date'] = date.text.strip()

            book_url = book.find('a')
            if book_url:
                js['url'] = '%s%s' % (self.mirror, book_url.get('href'))

            self.storage[self.page].append(js)
        self.result = self.storage[self.page]

    async def init(self):
        page = await self.fetch_page()
        self.parse_page(page)
        return self

    async def fetch_page(self):
        return await self.__r('%s&page=%d' % (self.__url, self.page))

    async def next_page(self):
        self.page += 1

        if not self.storage.get(self.page):
            page = await self.fetch_page()
            self.parse_page(page)
        
        self.result = self.storage[self.page]

    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
        else:
            return

        if not self.storage.get(self.page):
            page = await self.fetch_page()
            self.parse_page(page)
        
        self.result = self.storage[self.page]


class BookItem(dict):
    parsed = None

    def __init__(self, request, mirror):
        super().__init__()
        self.__r = request
        self.mirror = mirror

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
        if desc:
            parsed['description'] = desc.text.strip()

        details = wrap.find('div', { 'class': 'bookDetailsBox' })

        properties = [
                'year',
                'edition',
                'publisher',
                'language'
        ]
        for prop in properties:
            x = details.find('div', { 'class': 'property_' + prop })
            if x:
                x = x.find('div', { 'class': 'property_value' })
                parsed[prop] = x.text.strip()

        isbns = details.findAll('div', { 'class': 'property_isbn' })
        for isbn in isbns:
            txt = isbn.find('div', { 'class': 'property_label' }).text.strip(':')
            val = isbn.find('div', { 'class': 'property_value' })
            parsed[txt] = val.text.strip()

        cat = details.find('div', { 'class': 'property_categories' })
        if cat:
            cat = cat.find('div', { 'class': 'property_value' })
            link = cat.find('a')
            parsed['categories'] = cat.text.strip()
            parsed['categories_url'] = '%s%s' % (self.mirror, link.get('href'))

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
        
        if 'unavailable' in dl_link.text:
            parsed['download_url'] = 'Unavailable (use tor to download)'
        else:
            parsed['download_url'] = '%s%s' % (self.mirror, dl_link.get('href'))
        self.parsed = parsed
        return parsed


class BooklistItemPaginator(dict):
    __url = ""
    __pos = 0

    page = 1
    mirror = ""
    count = 10
    total = 0

    result = []

    storage = {
        1: []
    }

    def __init__(self, request, mirror, count: int = 10):
        super().__init__()
        self.__r = request
        self.mirror = mirror
        self.count = count

    async def fetch(self):
        parsed = {}
        parsed['url'] = self['url']
        parsed['name'] = self['name']

        get_id = self['url'].split('/')[-2]
        payload = "papi/booklist/%s/get-books" % get_id
        self.__url = "%s/%s" % (self.mirror, payload)

        await self.init()

        self.parsed = parsed
        return parsed

    async def init(self):
        fjs = await self.fetch_json()
        await self.parse_json(fjs)
        return self

    async def parse_json(self, fjs):
        self.storage[self.page] = []

        fjs = json.loads(fjs)
        for book in fjs["books"]:
            js = BookItem(self.__r, self.mirror)

            js['id'] = book['book']['id']
            js['isbn'] = book['book']['identifier']

            book_url = book['book'].get('href')
            if book_url:
                js['url'] = '%s%s' % (self.mirror, book_url)

            js['cover'] = book['book'].get('cover')
            js['name'] = book['book'].get('title')

            js['publisher'] = book['book'].get('publisher')

            js['authors'] = book['book'].get('author').split(',')
    
            js['year'] = book['book'].get('year')
            js['language'] = book['book'].get('language')

            js['extension'] = book['book'].get('extension')
            js['size'] = book['book'].get('filesizeString')

            js['rating'] = book['book'].get('qualityScore')

            self.storage[self.page].append(js)

        count = fjs['pagination']['total_pages']
        self.total = int(count)

    async def fetch_json(self):
        return await self.__r('%s/%d' % (self.__url, self.page))

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
            self.__pos -= self.count
            if self.__pos < 0:
                self.__pos = 0

        if not self.storage.get(self.page):
            json = await self.fetch_json()
            await self.parse_json(json)

    async def prev_page(self):
        if self.page > 1:
            self.page -= 1
        else:
            self.__pos = 0
            return

        if not self.storage.get(self.page):
            json = await self.fetch_json()
            await self.parse_json(json)

        self.__pos = len(self.storage[self.page])

