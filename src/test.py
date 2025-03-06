from zlibrary import AsyncZlib, booklists
import asyncio
import logging
import os

logging.getLogger("zlibrary").addHandler(logging.StreamHandler())
logging.getLogger("zlibrary").setLevel(logging.DEBUG)


async def main():
    lib = AsyncZlib()
    await lib.login(os.environ.get('ZLOGIN'), os.environ.get('ZPASSW'))

    booklist = await lib.profile.search_public_booklists("test")
    assert len(booklist.storage) > 0

    # count: 10 results per set
    paginator = await lib.search(q="biology", count=10)
    await paginator.next()

    assert len(paginator.result) > 0
    print(paginator.result)

    # fetching next result set (10 ... 20)
    next_set = await paginator.next()

    assert len(next_set) > 0
    print(next_set)

    # get back to previous set (0 ... 10)
    prev_set = await paginator.prev()

    assert len(prev_set) > 0
    print(prev_set)

    book = await paginator.result[0].fetch()
    assert book.get('name')
    print(book)

    book = await lib.get_by_id('5393918/a28f0c')
    assert book.get('name')
    print(book)


if __name__ in '__main__':
    asyncio.run(main())
