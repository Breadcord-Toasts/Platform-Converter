import datetime


class UniversalAlbum:
    def __init__(
        self,
        *,
        title: str,
        artist_names: list[str],
        url: str,
        release_date: datetime.datetime | None = None,
        cover_url: str | None = None,
    ):
        self.title = title
        self.artist_names = artist_names
        self.url = url
        self.cover_url = cover_url
        self.release_date = release_date

    def __str__(self):
        return f"{self.title} by {', '.join(self.artist_names)}"

    def __repr__(self):
        return (
            f"<UniversalAlbum"
            f" title={self.title!r}"
            f" artist_names={self.artist_names!r}"
            f" url={self.url!r}"
            f" cover_url={self.cover_url!r}"
            f" release_date={self.release_date!r}"
            f">"
        )


class UniversalTrack:
    def __init__(
        self,
        *,
        title: str,
        artist_names: list[str],
        url: str,
        cover_url: str | None = None,
        album: UniversalAlbum | None = None,
    ):
        self.title = title
        self.artist_names = artist_names
        self.url = url
        self.album = album
        self.cover_url = cover_url

    def __str__(self):
        return f"{self.title} by {', '.join(self.artist_names)}"

    def __repr__(self):
        return (
            f"<UniversalTrack"
            f" title={self.title!r}"
            f" artists={self.artist_names!r}"
            f" url={self.url!r}"
            f" album={self.album!r}"
            f" cover_url={self.cover_url!r}"
            f">"
        )


class UniversalPlaylist:
    def __init__(
        self,
        *,
        name: str,
        description: str | None,
        owner_names: list[str] | None,
        url: str,
        tracks: list[UniversalTrack],
        cover_url: str | None = None,
    ):
        self.name = name
        self.description = description
        self.owner_names = owner_names
        self.url = url
        self.tracks = tracks
        self.cover_url = cover_url

    def __str__(self):
        return f"Playlist {self.name} by {', '.join(self.owner_names)}"

    def __repr__(self):
        return (
            f"<UniversalPlaylist"
            f" name={self.name!r}"
            f" owner_names={self.owner_names!r}"
            f" url={self.url!r}"
            f" tracks={self.tracks!r}"
            f" cover_url={self.cover_url!r}"
            f">"
        )
