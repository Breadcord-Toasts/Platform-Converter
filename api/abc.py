from abc import abstractmethod, ABC
from datetime import datetime, timedelta

import aiohttp

from .errors import InvalidURLError
from .universals import UniversalTrack, UniversalPlaylist

__all__ = [
    'AbstractAPI',
    'AbstractOAuthAPI',
    'AbstractPlaylistAPI',
]


class AbstractAPI(ABC):
    def __init__(self, *, session: aiohttp.ClientSession):
        self.session = session

    def is_valid_track_url(self, track_url: str, /) -> bool:
        try:
            self.get_track_id(track_url)
        except InvalidURLError:
            return False
        else:
            return True

    @abstractmethod
    def get_track_id(self, track_url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def track_from_id(self, track_id: str) -> UniversalTrack | None:
        raise NotImplementedError

    @abstractmethod
    async def search_tracks(self, query: str) -> list[UniversalTrack] | None:
        raise NotImplementedError


class AbstractOAuthAPI(AbstractAPI, ABC):
    def __init__(self, *, client_id: str, client_secret: str, session: aiohttp.ClientSession):
        super().__init__(session=session)
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def should_update_token(self) -> bool:
        leniency = timedelta(minutes=15)
        return self._token_expires_at is None or self._token_expires_at < datetime.now() + leniency

    @abstractmethod
    async def refresh_access_token(self):
        raise NotImplementedError


class AbstractPlaylistAPI(ABC):
    async def is_valid_playlist_url(self, playlist_url: str, /) -> bool:
        try:
            self.get_playlist_id(playlist_url)
        except InvalidURLError:
            return False
        else:
            return True

    @abstractmethod
    def get_playlist_id(self, playlist_url: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_playlist_content(self, playlist_id: str) -> UniversalPlaylist | None:
        raise NotImplementedError
