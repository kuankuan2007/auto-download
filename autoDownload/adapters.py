import requests
import requests.adapters

from requests import Response


class Adapter(object):
    """
    A class to manage a collection of adapters.
    """

    session: requests.Session

    def __init__(self, session: requests.Session | None = None):
        """
        Initialize the Adapters object with an empty list of adapters.
        """
        self.session = session or requests.Session()

    def request(self, *args, **kw):
        """
        At the lowest level is the function that sends the request most directly.
        Do not change any business-level configuration here.
        """
        return self.session.request(*args, **kw)


defaultAdapters = Adapter()

__all__ = ["defaultAdapters", "Adapter", "Response"]
