class AuthenticationException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class EndOfStreamException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class NegotiationException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)

class ConnectionTimeoutException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)