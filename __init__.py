import asyncio
import io
import re

import discord
from discord import app_commands
from discord.ext import commands

import breadcord
from .api import helpers
from .api.abc import AbstractAPI, AbstractOAuthAPI, AbstractPlaylistAPI
from .api.errors import InvalidURLError
from .api.helpers import track_embed, track_to_query, url_to_file
from .api.platforms import SpotifyAPI
from .api.types import APIInterface
from .api.universals import UniversalTrack


class PlatformConverter(helpers.PlatformAPICog):
    def __init__(self, module_id: str):
        super().__init__(module_id)

        self.ctx_menu = app_commands.ContextMenu(
            name="Convert music/video URLs",
            callback=self.url_convert_ctx_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    # noinspection PyUnusedLocal
    async def platform_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=platform, value=platform)
            for platform in breadcord.helpers.search_for(
                current,
                tuple(self.api_interfaces.keys())
            )
        ]

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(
        from_platform=platform_autocomplete, # type: ignore
        to_platform=platform_autocomplete, # type: ignore
    )
    async def track_convert(self, ctx: commands.Context, from_platform: str, to_platform: str, url: str):
        """Converts music from one platform to another

        Parameters
        -----------
        from_platform: str
            The platform to convert from
        to_platform: str
            The platform to convert to
        url: str
            The url to the track to convert
        """
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]

        from_platform = self.api_interfaces.get(from_platform.lower())
        to_platform = self.api_interfaces.get(to_platform.lower())
        if not all((from_platform, to_platform)):
            await ctx.reply("Unknown platform")
            return

        try:
            track_id = from_platform.get_track_id(url)
        except InvalidURLError:
            await ctx.reply("Invalid url")
            return
        query = track_to_query(await from_platform.track_from_id(track_id))

        tracks = await to_platform.search_tracks(query)
        if not tracks:
            await ctx.reply("No results found")
            return
        await ctx.reply(tracks[0].url)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.settings.disliked_platforms.value:
            return
        if urls := await self.convert_message_urls(message):
            await message.reply(urls, mention_author=False)

    async def url_convert_ctx_menu(self, interaction: discord.Interaction, message: discord.Message) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        await interaction.followup.send(await self.convert_message_urls(message) or "Nothing to convert")

    async def convert_message_urls(self, message: discord.Message) -> str | None:
        preferred_platform_interface = self.api_interfaces.get(self.settings.preferred_platform.value)
        if preferred_platform_interface is None:
            raise ValueError("No valid preferred platform is set")

        if not (urls := re.findall(r"<?(?:https:|http:)\S+>?", message.content)):
            return

        async def convert_url(url: str) -> str:
            for api_interface in self.api_interfaces.values():
                if api_interface == preferred_platform_interface:
                    continue
                try:
                    track_id = api_interface.get_track_id(url)
                except InvalidURLError:
                    continue

                query = track_to_query(await api_interface.track_from_id(track_id))
                tracks = await preferred_platform_interface.search_tracks(query)
                return tracks[0].url

        converted_urls = tuple(filter(bool, await asyncio.gather(*map(convert_url, urls))))
        return " ".join(converted_urls) or None

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(platform=platform_autocomplete) # type: ignore
    async def search(
        self,
        ctx: commands.Context,
        platform: helpers.PlatformConverter,
        *,
        query: str,
        count: int = 1,
        compact_embeds: bool = False
    ):
        """Search for music/videos across several platforms¤

        Parameters
        -----------
        platform: APIInterface
            The platform to search on
        query: str
            Your search query
        count: int
            The maximum amount of urls to return
        """
        platform: APIInterface | None
        if platform is None:
            await ctx.reply("Invalid platform! Available platforms are: " + ", ".join(map(
                lambda x: f"`{x}`",
                self.api_interfaces
            )))
            return

        await ctx.defer()
        results = await platform.search_tracks(query)
        if compact_embeds:
            embeds = []
            files = []
            for i, result in enumerate(results[:min(10, max(1, count))]):
                result: UniversalTrack
                files.append(discord.File(
                    await url_to_file(result.cover_url, session=self.session),
                    filename=f"{i}.png"
                ))
                embeds.append(track_embed(result, random_colour=True, cover_url=f"attachment://{i}.png"))
            await ctx.reply(embeds=embeds, files=files)
        else:
            await ctx.reply(" ".join(result.url for result in results[:max(1, count)]))

    # noinspection PyUnusedLocal
    async def playlist_platform_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=platform, value=platform)
            for platform in breadcord.helpers.search_for(
                current,
                [
                    platform
                    for platform, api_interface in self.api_interfaces.items()
                    if isinstance(api_interface, AbstractPlaylistAPI)
                ]
            )
        ]

    @commands.hybrid_command()
    @app_commands.autocomplete(platform=playlist_platform_autocomplete) # type: ignore
    async def playlist_info(
        self,
        ctx: commands.Context,
        platform: helpers.PlatformConverter,
        playlist_url: str,
        max_tracks: int = 15
    ):
        platform: APIInterface | None  # guh
        if not isinstance(platform, AbstractPlaylistAPI):
            await ctx.reply("Invalid platform! Available platforms with playlist support are: " + ", ".join([
                f"`{platform}`"
                for platform in self.api_interfaces
                if isinstance(self.api_interfaces[platform], AbstractPlaylistAPI)
            ]))
            return

        try:
            playlist_id = platform.get_playlist_id(playlist_url)
        except InvalidURLError:
            await ctx.reply("Invalid playlist url")
            return
        playlist = await platform.get_playlist_content(playlist_id)
        if playlist is None:
            await ctx.reply("Could not find that playlist. Ensure that it exists and is public.")
            return

        description = discord.utils.escape_markdown(playlist.description.strip()) if playlist.description else ""
        description += "\n\n**Tracks**"
        for i, track in enumerate(playlist.tracks):
            title = discord.utils.escape_markdown(track.title)
            artists = ", ".join(map(discord.utils.escape_markdown, track.artist_names))

            fallback_text = f"\n\nAnd {len(playlist.tracks) - i} more..." if i != len(playlist.tracks) - 1 else ""
            addition = f"{i + 1}. [{title}]({track.url}) - {artists}"
            if len(description) + len(addition) + len(fallback_text) >= 4096 or i >= max_tracks:
                description += fallback_text
                break
            description += f"\n{addition}"

        cover = discord.File(
            await url_to_file(playlist.cover_url, session=self.session),
            filename="cover.png"
        )
        await ctx.reply(
            embed=discord.Embed(
                title=playlist.name,
                description=description,
                url=playlist.url,
                colour=discord.Colour.random(seed=playlist.url),
            ).set_thumbnail(
                url="attachment://cover.png"
            ).set_footer(
                text=f"By {', '.join(playlist.owner_names)}" if playlist.owner_names else None,
            ),
            file=cover
        )

    # noinspection PyIncorrectDocstring
    @commands.hybrid_command()
    @app_commands.autocomplete(
        from_platform=playlist_platform_autocomplete,  # type: ignore
        to_platform=platform_autocomplete,  # type: ignore
    )
    async def playlist_convert(
        self,
        ctx: commands.Context,
        from_platform: str,
        to_platform: str,
        url: str,
        start_index: int = 1,
    ):
        """Converts playlists from one platform to another

        Parameters
        -----------
        from_platform: str
            The platform to convert from
        to_platform: str
            The platform to convert to
        url: str
            The url to the playlist to convert
        start_index: int
            The track to start converting from.
            Starts at 1 and includes the track at that index
        """
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1]

        from_platform = self.api_interfaces.get(from_platform.lower())
        to_platform = self.api_interfaces.get(to_platform.lower())
        if not all((isinstance(from_platform, AbstractPlaylistAPI), isinstance(to_platform, AbstractAPI))):
            await ctx.reply("Unknown platform")
            return

        playlist = await from_platform.get_playlist_content(from_platform.get_playlist_id(url))
        if not playlist or not playlist.tracks:
            await ctx.reply("Could not find that playlist. Ensure that it exists and is public.")
            return

        run_by_owner = await self.bot.is_owner(ctx.author)
        if not run_by_owner and len(playlist.tracks) > self.settings.max_convert_playlist_size.value:
            await ctx.reply(
                f"This playlist is too big to convert in a reasonable amount of time, "
                f"only the first {self.settings.max_convert_playlist_size.value} tracks will be converted.\n"
                f"This may take a while..."
            )
        else:
            await ctx.reply("Converting tracks. This may take a while...")

        if not run_by_owner:
            playlist.tracks = playlist.tracks[:self.settings.max_convert_playlist_size.value]
        playlist.tracks = playlist.tracks[start_index - 1:]

        converted_track_urls = []
        for track in playlist.tracks:
            query = track_to_query(track)
            if converted_track := await to_platform.search_tracks(query):
                converted_track_urls.append(converted_track[0].url)
            else:
                converted_track_urls.append("Could not be found")
            # Give the API some time to breathe
            await asyncio.sleep(0.5)

        if not converted_track_urls or all(url == "Could not be found" for url in converted_track_urls):
            await ctx.reply("No results found")
            return

        def supress_embed(to_supress: str, /) -> str:
            return f"<{to_supress}>"

        to_send = (f"# Finished converting tracks\n"
                   f"Converted from: <{url}>\n\n")
        for i, url in enumerate(map(supress_embed, converted_track_urls), start=1):
            if len(to_send) + len(url) >= 2000:
                await ctx.channel.send(to_send)
                to_send = ""
            to_send += f"{i}. {url}\n"

        # A file listing all the converted urls
        file = discord.File(
            fp=io.BytesIO("\n".join(converted_track_urls).encode("utf-8")),
            filename="converted_tracks.txt"
        )

        if to_send:
            await ctx.channel.send(to_send, file=file)

    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(str(error), ephemeral=True)
            return
        raise


async def setup(bot: breadcord.Bot):
    await bot.add_cog(PlatformConverter("platform_converter"))
