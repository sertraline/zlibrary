

class LoopError(Exception):

    def __init__(self, message):
        super().__init__(message)


class ParseError(Exception):

    def __init__(self, message):
        super().__init__(message)


class NoDomainError(Exception):

    def __init__(self):
        super().__init__("No working domains have been found. Try again later.")


class EmptyQueryError(Exception):

    def __init__(self):
        super().__init__("Search query is empty.")


class ProxyNotMatchError(Exception):

    def __init__(self):
        super().__init__("proxy_list must be a list.")


class NoProfileError(Exception):

    def __init__(self):
        super().__init__("You have to log in into your singlelogin.me account to access zlibrary. Use login() before performing the search.")