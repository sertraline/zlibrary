# zlibrary
(prototype)


### Example
```python
import zlibrary
import asyncio


async def main():
    lib = zlibrary.AsyncZlib()
    # init fires up a request to check currently available domain
    await lib.init()

    # count: 10 results per set
    paginator = await lib.search(q="biology", count=10)
    # fetching first result set (0 ... 10)
    first_set = await paginator.next()
    # fetching next result set (10 ... 20)
    next_set = await paginator.next()
    # get back to previous set (0 ... 10)
    prev_set = await paginator.prev()
    # trying to go back will result in rolling over:
    # here you try to go (-10 ... 0). Because it is the first page results roll over to (40 ... 50) of the same page.
    roll = await paginator.prev()

    # create a paginator of computer science with max count of 50
    paginator_cs = await lib.search(q="computer science", count=50)
    # fetching results (0 ... 50)
    next_set = await paginator_cs.next()
    # calling another next_set will fire up a request to fetch the next page
    next_set = await paginator_cs.next()

    # get current result set
    current_set = paginator.result

    # switch pages explicitly
    await paginator.next_page()

    # here, no requests are being made: results are cached
    await paginator.prev_page()
    await paginator.next_page()


if __name__ == '__main__':
    asyncio.run(main())
```  

### Enable logging  
Put anywhere in your code:  

```python
import logging

logging.getLogger("zlibrary").addHandler(logging.StreamHandler())
logging.getLogger("zlibrary").setLevel(logging.DEBUG)
```  
