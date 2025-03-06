from typing import Callable, Optional
from bs4 import BeautifulSoup as bsoup
from bs4 import Tag
from urllib.parse import quote

from .exception import ParseError
from .logger import logger

import json


DLNOTFOUND = "Downloads not found"
LISTNOTFOUND = "On your request nothing has been found"


class SearchPaginator:
    __url = ""
    __pos = 0
    __r: Optional[Callable] = None

    mirror = ""
    page = 1
    total = 0
    count = 10

    result = []

    storage = {1: []}

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
        return f"<Paginator [{self.__url}], count {self.count}, len(result): {len(self.result)}, pages in storage: {len(self.storage.keys())}>"

    def parse_page(self, page):
        soup = bsoup(page, features="lxml")
        box = soup.find("div", {"id": "searchResultBox"})
        if not box or type(box) is not Tag:
            raise ParseError("Could not parse book list.")

        check_notfound = soup.find("div", {"class": "notFound"})
        if check_notfound:
            logger.debug("Nothing found.")
            self.storage[self.page] = []
            self.result = []
            return

        with open("test.html", "w") as f:
            f.write(str(box.prettify()))
        book_list = box.findAll("div", {"class": "book-item"})
        if not book_list:
            raise ParseError("Could not find the book list.")

        self.storage[self.page] = []

        for idx, book in enumerate(book_list, start=1):
            js = BookItem(self.__r, self.mirror)

            book = book.find("z-bookcard")
            cover = book.find("img")
            if not cover:
                logger.debug(f"Failure to parse {idx}-th book at url {self.__url}")
                continue

            js["id"] = book.get("id")
            js["isbn"] = book.get("isbn")

            book_url = book.get("href")
            if book_url:
                js["url"] = f"{self.mirror}{book_url}"
            img = cover.find("img")
            if img:
                js["cover"] = img.get("data-src")

            publisher = book.get("publisher")
            if publisher:
                js["publisher"] = publisher.strip()

            slot = book.find("div", {"slot": "author"})
            if slot and slot.text:
                authors = slot.text.split(";")
                authors = [i.strip() for i in authors if i]
                if authors:
                    js["authors"] = authors

            title = book.find("div", {"slot": "title"})
            if title and title.text:
                js["name"] = title.text.strip()

            year = book.get("year")
            if year:
                js["year"] = year.strip()

            lang = book.get("language")
            if lang:
                js["language"] = lang.strip()

            ext = book.get("extension")
            if ext:
                js["extension"] = ext.strip()

            size = book.get("filesize")
            if size:
                js["size"] = size.strip()

            rating = book.get("rating")
            if rating:
                js["rating"] = rating.strip()

            quality = book.get("quality")
            if quality:
                js["quality"] = quality.strip()

            self.storage[self.page].append(js)

        scripts = soup.findAll("script")
        for scr in scripts:
            txt = scr.text
            if "var pagerOptions" in txt:
                pos = txt.find("pagesTotal: ")
                fix = txt[pos + len("pagesTotal: ") :]
                count = fix.split(",")[0]
                self.total = int(count)

    async def init(self):
        page = await self.fetch_page()
        self.parse_page(page)

    async def fetch_page(self):
        if self.__r:
            return await self.__r(f"{self.__url}&page={self.page}")

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
    __r: Optional[Callable] = None

    mirror = ""
    page = 1
    total = 1
    count = 10

    result = []

    storage = {1: []}

    def __init__(self, url: str, count: int, request: Callable, mirror: str):
        self.count = count
        self.__url = url
        self.__r = request
        self.mirror = mirror

    def __repr__(self):
        return f"<Booklist paginator [{self.__url}], count {self.count}, len(result): {len(self.result)}, pages in storage: {len(self.storage.keys())}>"

    def parse_page(self, page):
        soup = bsoup(page, features="lxml")

        check_notfound = soup.find("div", {"class": "cBox1"})
        if check_notfound and LISTNOTFOUND in check_notfound.text.strip():
            logger.debug("Nothing found.")
            self.storage[self.page] = []
            self.result = []
            return

        book_list = soup.findAll("z-booklist")
        if not book_list:
            raise ParseError("Could not find the booklists.")

        self.storage[self.page] = []

        for idx, booklist in enumerate(book_list, start=1):
            js = BooklistItemPaginator(self.__r, self.mirror, self.count)

            name = booklist.get("topic")
            if not name:
                raise ParseError(
                    f"Could not parse {idx}-th booklist at url {self.__url}"
                )
            js["name"] = name.strip()

            book_url = booklist.get("href")
            if book_url:
                js["url"] = f"{self.mirror}{book_url}"

            info_wrap = booklist.get("description")
            if info_wrap:
                js["description"] = info_wrap.strip()

            author = booklist.get("authorprofile")
            if author:
                js["author"] = author.strip()

            count = booklist.get("quantity")
            if count:
                js["count"] = count.strip()

            views = booklist.get("views")
            if views:
                js["views"] = views.strip()

            js["books_lazy"] = []
            carousel = booklist.find_all("a")
            if not carousel:
                self.storage[self.page].append(js)
                continue
            for adx, book in enumerate(carousel):
                res = BookItem(self.__r, self.mirror)
                res["url"] = f"{self.mirror}{book.get('href')}"
                res["name"] = ""

                zcover = book.find("z-cover")
                if zcover:
                    b_id = zcover.get("id")
                    if b_id:
                        res["id"] = b_id.strip()
                    b_au = zcover.get("author")
                    if b_au:
                        res["author"] = b_au.strip()
                    b_name = zcover.get("title")
                    if b_name:
                        res["name"] = b_name.strip()
                    cover = zcover.find_all("img")
                    if cover:
                        for c in cover:
                            d_src = c.get("data-src")
                            if d_src:
                                js["cover"] = d_src.strip()

                js["books_lazy"].append(res)

            self.storage[self.page].append(js)

        scripts = soup.findAll("script")
        for scr in scripts:
            txt = scr.text
            if "var pagerOptions" in txt:
                pos = txt.find("pagesTotal: ")
                fix = txt[pos + len("pagesTotal: ") :]
                count = fix.split(",")[0]
                self.total = int(count)

    async def init(self):
        page = await self.fetch_page()
        self.parse_page(page)
        return self

    async def fetch_page(self):
        if self.__r:
            return await self.__r(f"{self.__url}&page={self.page}")

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

    storage = {1: []}

    def __init__(self, url: str, page: int, request: Callable, mirror: str):
        self.__url = url
        self.__r = request
        self.mirror = mirror
        self.page = page

    def __repr__(self):
        return f"<Downloads paginator [{self.__url}]>"

    def parse_page(self, page):
        soup = bsoup(page, features="lxml")
        box = soup.find("div", {"class": "dstats-content"})
        if not box or type(box) is not Tag:
            raise ParseError("Could not parse downloads list.")

        check_notfound = box.find("p")
        if check_notfound and DLNOTFOUND in check_notfound.text.strip():
            logger.debug("This page is empty.")
            self.storage[self.page] = []
            self.result = []
            return

        book_list = box.findAll("tr", {"class": "dstats-row"})
        if not book_list:
            raise ParseError("Could not find the book list.")

        self.storage[self.page] = []

        for _, book in enumerate(book_list, start=1):
            js = BookItem(self.__r, self.mirror)

            title = book.find("div", {"class": "book-title"})
            date = book.find("td", {"class": "lg-w-120"})

            js["name"] = title.text.strip()
            js["date"] = date.text.strip()

            book_url = book.find("a")
            if book_url:
                js["url"] = f"{self.mirror}{book_url.get('href')}"
            self.storage[self.page].append(js)
        self.result = self.storage[self.page]

    async def init(self):
        page = await self.fetch_page()
        self.parse_page(page)
        return self

    async def fetch_page(self):
        if self.__r:
            return await self.__r(f"{self.__url}&page={self.page}")

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
    __r: Optional[Callable] = None

    def __init__(self, request, mirror):
        super().__init__()
        self.__r = request
        self.mirror = mirror

    async def fetch(self):
        if not self.__r:
            raise ParseError("Instance of BookItem does not contain a request method.")
        page = await self.__r(self["url"])
        soup = bsoup(page, features="lxml")

        wrap = soup.find("div", {"class": "row cardBooks"})
        if not wrap or type(wrap) is not Tag:
            raise ParseError(f"Failed to parse {self['url']}")

        parsed = {}
        parsed["url"] = self["url"]

        zcover = soup.find("z-cover")
        if not zcover or type(zcover) is not Tag:
            raise ParseError(f"Failed to find zcover in {self['url']}")

        col = wrap.find("div", {"class": "col-sm-9"})
        if col and type(col) is Tag:
            anchors = col.find_all("a")
            if anchors:
                parsed["authors"] = []
                for anchor in anchors:
                    parsed["authors"].append(
                        {
                            "author": anchor.text.strip(),
                            "author_url": f"{self.mirror}{quote(anchor.get('href'))}",
                        }
                    )

        title = zcover.get("title")
        if title:
            if type(title) is list[str]:
                parsed["name"] = title[0].strip()
            elif type(title) is str:
                parsed["name"] = title.strip()

        cover = zcover.find("img", {"class": "image"})
        if cover and type(cover) is Tag:
            parsed["cover"] = cover.get("src")

        desc = wrap.find("div", {"id": "bookDescriptionBox"})
        if desc:
            parsed["description"] = desc.text.strip()

        details = wrap.find("div", {"class": "bookDetailsBox"})

        properties = ["year", "edition", "publisher", "language"]
        for prop in properties:
            if type(details) is Tag:
                x = details.find("div", {"class": "property_" + prop})
                if x and type(x) is Tag:
                    x = x.find("div", {"class": "property_value"})
                    if x:
                        parsed[prop] = x.text.strip()

        if type(details) is Tag:
            isbns = details.findAll("div", {"class": "property_isbn"})
            for isbn in isbns:
                txt = isbn.find("div", {"class": "property_label"}).text.strip(":")
                val = isbn.find("div", {"class": "property_value"})
                parsed[txt] = val.text.strip()

            cat = details.find("div", {"class": "property_categories"})
            if cat and type(cat) is Tag:
                cat = cat.find("div", {"class": "property_value"})
                if cat and type(cat) is Tag:
                    link = cat.find("a")
                    if link and type(link) is Tag:
                        parsed["categories"] = cat.text.strip()
                        parsed["categories_url"] = f"{self.mirror}{link.get('href')}"

            file = details.find("div", {"class": "property__file"})
            if file and type(file) is Tag:
                file = file.text.strip().split(",")
                parsed["extension"] = file[0].split("\n")[1]
                parsed["size"] = file[1].strip()

        rating = wrap.find("div", {"class": "book-rating"})
        if rating and type(rating) is Tag:
            parsed["rating"] = "".join(
                filter(lambda x: bool(x), rating.text.replace("\n", "").split(" "))
            )

        dl_btn = soup.find("a", {"class": "btn btn-default addDownloadedBook"})
        if dl_btn and type(dl_btn) is Tag:
            if "unavailable" in dl_btn.text:
                parsed["download_url"] = "Unavailable (use tor to download)"
            else:
                parsed["download_url"] = f"{self.mirror}{dl_btn.get('href')}"
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

    storage = {1: []}

    def __init__(self, request, mirror, count: int = 10):
        super().__init__()
        self.__r = request
        self.mirror = mirror
        self.count = count

    async def fetch(self):
        parsed = {}
        parsed["url"] = self["url"]
        parsed["name"] = self["name"]

        get_id = self["url"].split("/")[-2]
        payload = f"papi/booklist/{get_id}/get-books"
        self.__url = f"{self.mirror}/{payload}"

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

            js["id"] = book["book"]["id"]
            js["isbn"] = book["book"]["identifier"]

            book_url = book["book"].get("href")
            if book_url:
                js["url"] = f"{self.mirror}{book_url}"

            js["cover"] = book["book"].get("cover")
            js["name"] = book["book"].get("title")

            js["publisher"] = book["book"].get("publisher")

            js["authors"] = book["book"].get("author").split(",")

            js["year"] = book["book"].get("year")
            js["language"] = book["book"].get("language")

            js["extension"] = book["book"].get("extension")
            js["size"] = book["book"].get("filesizeString")

            js["rating"] = book["book"].get("qualityScore")

            self.storage[self.page].append(js)

        count = fjs["pagination"]["total_pages"]
        self.total = int(count)

    async def fetch_json(self):
        return await self.__r(f"{self.__url}/{self.page}")

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
