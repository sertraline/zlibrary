

class LoopError(Exception):

    def __init__(self, message):
        super().__init__(message)


class ParseError(Exception):

    def __init__(self, message):
        super().__init__(message)


class NoDomainError(Exception):

    def __init__(self):
        super().__init__("No working domain found. Try another time.")


class EmptyQueryError(Exception):

    def __init__(self):
        super().__init__("Search query is empty.")
