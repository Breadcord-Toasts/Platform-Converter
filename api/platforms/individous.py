import re

from ..abc import AbstractAPI, AbstractPlaylistAPI
from ..errors import InvalidURLError
from ..universals import UniversalTrack, UniversalPlaylist


def invidious_video_to_universal(video: dict, *, instance_url: str) -> UniversalTrack:
    return UniversalTrack(
        title=video["title"],
        artist_names=[video["author"]],
        url=f"{instance_url}/watch?v={video['videoId']}",
        cover_url=video["videoThumbnails"][0]["url"],
    )


class InvidiousAPI(AbstractAPI, AbstractPlaylistAPI):
    def __init__(self, *args, invidious_instance_url: str = "https://yt.artemislena.eu", **kwargs):
        super().__init__(*args, **kwargs)
        self.invidious_instance_url = invidious_instance_url.removesuffix("/")

    def get_track_id(self, track_url: str) -> str:
        # Flawed regex, but what can you do when the domain could be anything
        if matches := re.match(
            r"^(?:https?://)?.+\..+watch\?v=([a-zA-Z0-9_\-]+)",
            track_url,
            flags=re.ASCII,
        ):
            return matches[1]
        else:
            raise InvalidURLError("Invalid invidious video url")

    async def track_from_id(self, track_id: str) -> UniversalTrack | None:
        async with self.session.get(
            f"{self.invidious_instance_url}/api/v1/videos/{track_id}"
            f"?fields=title,author,videoId,videoThumbnails"
        ) as response:
            data = await response.json()
            return invidious_video_to_universal(data, instance_url=self.invidious_instance_url)

    async def search_tracks(self, query: str) -> list[UniversalTrack] | None:
        async with self.session.get(
            f"{self.invidious_instance_url}/api/v1/search?q={query}"
            f"&fields=title,author,videoId,videoThumbnails,type"
        ) as response:
            videos = filter(
                lambda vid: vid["type"] == "video",
                await response.json(),
            )
            return [invidious_video_to_universal(video, instance_url=self.invidious_instance_url) for video in videos]

    def get_playlist_id(self, playlist_url: str) -> str:
        if matches := re.match(
            r"^(?:https?://)?.+\..+playlist\?list=([a-zA-Z0-9_\-]+)",
            playlist_url,
            flags=re.ASCII,
        ):
            return matches[1]
        else:
            raise InvalidURLError("Invalid invidious playlist url")

    async def get_playlist_content(self, playlist_id: str) -> UniversalPlaylist | None:
        async with self.session.get(
            f"{self.invidious_instance_url}/api/v1/playlists/{playlist_id}"
        ) as response:
            playlist_info = await response.json()
            return UniversalPlaylist(
                name=playlist_info["title"],
                description=playlist_info.get("description"),
                owner_names=[playlist_info["author"]],
                url=f"{self.invidious_instance_url}/playlist?list={playlist_id}",
                cover_url=playlist_info["videos"][0]["videoThumbnails"][0]["url"],
                tracks=[
                    invidious_video_to_universal(video, instance_url=self.invidious_instance_url)
                    for video in playlist_info["videos"]
                ]
            )