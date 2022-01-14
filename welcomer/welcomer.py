import random
from typing import Literal
import typing
import urllib

import discord
from discord.errors import InvalidArgument
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError, URLError
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

MEMBER_NAME_TOKEN = "$MEMBER_NAME$"
SERVER_NAME_TOKEN = "$SERVER_NAME$"
MEMBER_COUNT_TOKEN = "$MEMBER_COUNT$"


def replace_tokens(text, member: discord.Member, use_mentions: typing.Optional[bool] = False):
    return text.replace(
        MEMBER_NAME_TOKEN, member.display_name if not use_mentions else member.mention
    ).replace(
        SERVER_NAME_TOKEN, member.guild.name
    ).replace(
        MEMBER_COUNT_TOKEN, str(member.guild.member_count)
    )


DEFAULT_GUILD = {
    "channel_id": None,
    "greeting": {
        "name": "Greeting messages",
        "enabled": False,
        "use_embed": True,
        "color": discord.Color.dark_green().to_rgb(),
        "title": f"Welcome to the {SERVER_NAME_TOKEN} discord, {MEMBER_NAME_TOKEN}!",
        "messages": [
            "Please read the **#information** channel for everything you need to know about this server!"
        ],
        "embed_image_url": "",
        "footer": f"You are member #{MEMBER_COUNT_TOKEN}!"
    },
    "departure": {
        "name": "Departure messages",
        "enabled": False,
        "use_embed": False,
        "color": discord.Color.dark_red().to_rgb(),
        "title": "",
        "messages": [
            f"**{MEMBER_NAME_TOKEN}** has left us.  Press :regional_indicator_f: to pay respects."
        ],
        "embed_image_url": "",
        "footer": ""
    }
}


class Welcomer(commands.Cog):
    """
    Welcomes new users with a greeting, and announces departures from the server.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)
        pass

    async def _toggle(self, ctx, obj):
        return await self._enabled(ctx, obj, not obj["enabled"])

    async def _enable(self, ctx, obj):
        return await self._enabled(ctx, obj, True)

    async def _disable(self, ctx, obj):
        return await self._enabled(ctx, obj, False)

    async def _enabled(self, ctx, obj, bool: typing.Optional[bool] = None):
        if bool is not None:
            obj["enabled"] = bool

        status_msg = ""

        if obj["enabled"]:
            status_msg = "**ENABLED**"
        else:
            status_msg = "**DISABLED**"

        await ctx.send(f"{obj['name']} are currently {status_msg}.")
        return obj

    async def _list(self, ctx, obj):
        embed = discord.Embed()
        embed.title = obj["name"]

        messages = []

        for i in range(len(obj["messages"])):
            messages.append(f"[{i}] {obj['messages'][i]}")

        embed.description = '\n'.join(messages)

        await ctx.send(embed=embed)
        return obj

    async def _add(self, ctx, obj, str):
        obj["messages"].append(str)
        await ctx.send(f"Added the following string to {obj['name']}:\n{str}")
        return obj

    async def _remove(self, ctx, obj, int):
        if int >= len(obj["messages"]):
            raise InvalidArgument(
                "Couldn't find the message at the given index.")

        str = obj["messages"].pop(int)
        await ctx.send(f"Removed the following string to {obj['name']}:\n{str}")
        return obj

    async def _use_embed(self, ctx, obj, bool: typing.Optional[bool] = None):
        if bool is not None:
            obj["use_embed"] = bool

        status_msg = ""

        if obj["use_embed"]:
            status_msg = "**RICH EMBED**"
        else:
            status_msg = "**SIMPLE**"

        await ctx.send(f"Currently configured to use {status_msg} {obj['name']}.")
        return obj

    async def _image(self, ctx, obj, url: typing.Optional[str] = None):
        prefix = "Currently"

        if url is not None:
            prefix = "Now"
            image_formats = ("image/png", "image/jpeg", "image/gif")
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0'}
                request = urllib.request.Request(url, headers=headers)
                site = urlopen(request)

                meta = site.info()  # get header of the http request

                if meta["content-type"] not in image_formats:
                    response = "``ERROR: Given URL is not a valid image.``"
                    await ctx.send(response)
                    return obj
            except (HTTPError, ValueError) as e:
                response = "``ERROR: Given parameter is not a valid url.``"
                await ctx.send(response)
                return obj

            obj["embed_image_url"] = url

        if obj["embed_image_url"] is None or obj["embed_image_url"] == "":
            await ctx.send(f"{prefix} no image thumbnail is set for use with rich embed {obj['name']}.")
        else:
            await ctx.send(f"{prefix} using the following image with rich embed {obj['name']}:\n{obj['embed_image_url']}")
        return obj

    async def _title(self, ctx, obj, title: typing.Optional[str] = None):
        prefix = "Currently"

        if title is not None:
            prefix = "Now"
            obj["title"] = title

        if obj["title"] is None or obj["title"] == "":
            await ctx.send(f"{prefix} no title is set for use with rich embed {obj['name']}.")
        else:
            await ctx.send(f"{prefix} using the following title with rich embed {obj['name']}:\n{obj['title']}")
        return obj

    async def _footer(self, ctx, obj, footer: typing.Optional[str] = None):
        prefix = "Currently"

        if footer is not None:
            prefix = "Now"
            obj["footer"] = footer

        if obj["footer"] is None or obj["footer"] == "":
            await ctx.send(f"{prefix} no footer is set for use with rich embed {obj['name']}.")
        else:
            await ctx.send(f"{prefix} using the following footer with rich embed {obj['name']}:\n{obj['footer']}")
        return obj

    async def _create_embed(self, channel: discord.TextChannel, obj, member: discord.Member):
        embed = discord.Embed()

        embed.title = replace_tokens(obj["title"], member)
        embed.description = replace_tokens(
            random.choice(obj["messages"]), member)
        embed.colour = discord.Color.from_rgb(*obj["color"])

        if obj["footer"] is not None and obj["footer"] != "":
            embed.set_footer(text=replace_tokens(obj["footer"], member), icon_url=member.avatar_url)

        if obj["embed_image_url"] is not None and obj["embed_image_url"] != "":
            embed.set_thumbnail(url=obj["embed_image_url"])

        await channel.send(embed=embed)
        return obj

    async def _create_simple(self, channel: discord.TextChannel, obj, member: discord.Member):
        title = replace_tokens(obj["title"], member, use_mentions=True)
        choice = replace_tokens(random.choice(
            obj["messages"]), member, use_mentions=True
        )
        await channel.send(f"{title} {choice}")
        return obj

    async def _create(self, channel: discord.TextChannel, obj, member: discord.Member):
        if len(obj["messages"]) < 1:
            raise InvalidArgument(
                f'There is no option available in the list for {obj["name"]}.')

        if obj["use_embed"]:
            return await self._create_embed(channel, obj, member)
        else:
            return await self._create_simple(channel, obj, member)

    @commands.group(name="welcomer")
    @commands.mod_or_permissions(manage_roles=True)
    async def settings(self, ctx: commands.Context):
        """Settings for controlling the server welcome and departure messages.
        """
        pass

    @settings.command()
    async def channel(self, ctx: commands.Context, channel: typing.Optional[discord.TextChannel] = None):
        """Sets or displays the current channel for welcome / departure announcements.

        Args:
            channel (discord.TextChannel): (Optional) The text channel for announcing.
        """
        if channel:
            await self.config.guild(ctx.guild).channel_id.set(channel.id)
            await ctx.send(f"Now broadcasting welcome and departure messages to {channel.mention}.")
            return
        else:
            channel_id = await self.config.guild(ctx.guild).channel_id()
            if channel_id is None:
                await ctx.send(f"There is no channel currently set for broadcasting greeting and departure messages!")
            else:
                channel = ctx.guild.get_channel(channel_id)
                await ctx.send(f"Currently broadcasting greeting and departure messages to {channel.mention}.")
            return

    @settings.group(aliases=["welcome"])
    async def greeting(self, ctx: commands.Context):
        """Commands for configuring the server greeting messages.
        """
        pass

    @greeting.command(name="toggle")
    async def greeting_toggle(self, ctx: commands.Context):
        """Toggles the greeting functionality for the bot.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._toggle(ctx, greeting)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="enable")
    async def greeting_enable(self, ctx: commands.Context):
        """Enables greeting messages for the server.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._enable(ctx, greeting)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="disable")
    async def greeting_disable(self, ctx: commands.Context):
        """Disables greeting messages for the server.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._disable(ctx, greeting)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="enabled")
    async def greeting_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of greeting messages for the server.

        Args: 
            bool (bool): (Optional) True / False
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._enabled(ctx, greeting, bool)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="list")
    async def greeting_list(self, ctx: commands.Context):
        """Gets the list of random greeting messages for the server.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._list(ctx, greeting)
        pass

    @greeting.command(name="add", help=f"""Adds a new greeting message for use in the server.  Use the following escaped strings for values:
        -- ``{MEMBER_NAME_TOKEN}`` - The target member's name
        -- ``{SERVER_NAME_TOKEN}`` - The server name
        -- ``{MEMBER_COUNT_TOKEN}`` - The server member count

        Args: 
        \tentry (str): The new greeting message to be used at random.
        """)
    async def greeting_add(self, ctx: commands.Context, *, entry: str):
        """Adds a new greeting message for use in the server.

        Args: 
            entry (str): The new greeting message to be used at random.
        """
        entry = entry.strip("\"\'")
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._add(ctx, greeting, entry)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="remove")
    async def greeting_remove(self, ctx: commands.Context, index: int):
        """Removes a greeting message for use in the server.

        Args: 
            index (int): The index of the greeting message to remove (use `welcomer greeting list` to verify the correct index).
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._remove(ctx, greeting, index)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="useembed")
    async def greeting_use_embed(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets greeting message type to Embeds or Simple.

        Args: 
            bool (bool): (Optional) True / False
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._use_embed(ctx, greeting, bool)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="image", aliases=["thumbnail"])
    async def greeting_image(self, ctx: commands.Context, *, url: typing.Optional[str] = None):
        """Sets the greeting message image thumbnail used in Rich Embed greeting messages.

        Args: 
            url (str): (Optional) A valid URL to the thumbnail image desired.
        """
        if url is not None:
            url = url.strip("\"\'")
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._image(ctx, greeting, url)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="title")
    async def greeting_title(self, ctx: commands.Context, *, title: typing.Optional[str] = None):
        """Sets the greeting message title used in Rich Embed greeting messages.

        Args: 
            title (str): (Optional) The title string to use in greeting messages.
        """
        if title is not None:
            title = title.strip("\"\'")
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._title(ctx, greeting, title)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @greeting.command(name="footer")
    async def greeting_footer(self, ctx: commands.Context, *, footer: typing.Optional[str] = None):
        """Sets the greeting message footer used in Rich Embed greeting messages.

        Args: 
            title (str): (Optional) The footer string to use in greeting messages.
        """
        if footer is not None:
            footer = footer.strip("\"\'")
        greeting = await self.config.guild(ctx.guild).greeting()
        greeting = await self._footer(ctx, greeting, footer)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass

    @settings.group(aliases=["leave"])
    async def departure(self, ctx: commands.Context):
        """Commands for configuring the server departure messages.
        """
        pass

    @departure.command(name="toggle")
    async def departure_toggle(self, ctx: commands.Context):
        """Toggles the departure functionality for the bot.
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._toggle(ctx, departure)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="enable")
    async def departure_enable(self, ctx: commands.Context):
        """Enables departure messages for the server.
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._enable(ctx, departure)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="disable")
    async def departure_disable(self, ctx: commands.Context):
        """Disables departure messages for the server.
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._disable(ctx, departure)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="enabled")
    async def departure_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of departure messages for the server.

        Args: 
            bool (bool): (Optional) True / False
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._enabled(ctx, departure, bool)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="list")
    async def departure_list(self, ctx: commands.Context):
        """Gets the list of random departure messages for the server.
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._list(ctx, departure)
        pass

    @departure.command(name="add", help=f"""Adds a new departure message for use in the server.  Use the following escaped strings for values:
        -- ``{MEMBER_NAME_TOKEN}`` - The target member's name
        -- ``{SERVER_NAME_TOKEN}`` - The server name
        -- ``{MEMBER_COUNT_TOKEN}`` - The server member count

        Args: 
        \tentry (str): The new departure message to be used at random.
        """)
    async def departure_add(self, ctx: commands.Context, *, entry: str):
        """Adds a new departure message for use in the server.

        Args: 
            entry (str): The new departure message to be used at random.
        """
        entry = entry.strip("\"\'")
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._add(ctx, departure, entry)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="remove")
    async def departure_remove(self, ctx: commands.Context, index: int):
        """Removes a departure message for use in the server.

        Args: 
            index (int): The index of the departure message to remove (use `welcomer departure list` to verify the correct index).
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._remove(ctx, departure, index)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="useembed")
    async def departure_use_embed(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets departure message type to Embeds or Simple.

        Args: 
            bool (bool): (Optional) True / False
        """
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._use_embed(ctx, departure, bool)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="image", aliases=["thumbnail"])
    async def departure_image(self, ctx: commands.Context, *, url: typing.Optional[str] = None):
        """Sets the departure message image thumbnail used in Rich Embed departure messages.

        Args: 
            url (str): (Optional) A valid URL to the thumbnail image desired.
        """
        if url is not None:
            url = url.strip("\"\'")
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._image(ctx, departure, url)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="title")
    async def departure_title(self, ctx: commands.Context, *, title: typing.Optional[str] = None):
        """Sets the departure message title used in Rich Embed departure messages.

        Args: 
            title (str): (Optional) The title string to use in departure messages.
        """
        if title is not None:
            title = title.strip("\"\'")
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._title(ctx, departure, title)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @departure.command(name="footer")
    async def departure_footer(self, ctx: commands.Context, *, footer: typing.Optional[str] = None):
        """Sets the departure message footer used in Rich Embed departure messages.

        Args: 
            title (str): (Optional) The footer string to use in departure messages.
        """
        if footer is not None:
            footer = footer.strip("\"\'")
        departure = await self.config.guild(ctx.guild).departure()
        departure = await self._footer(ctx, departure, footer)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires greeting messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """
        greeting = await self.config.guild(member.guild).greeting()

        if greeting["enabled"]:
            channel_id = await self.config.guild(member.guild).channel_id()
            channel = member.guild.get_channel(channel_id)

            if channel is not None:
                await self._create(channel, greeting, member)
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Fires departure messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """
        departure = await self.config.guild(member.guild).departure()

        if departure["enabled"]:
            channel_id = await self.config.guild(member.guild).channel_id()
            channel = member.guild.get_channel(channel_id)

            if channel is not None:
                await self._create(channel, departure, member)
        pass
