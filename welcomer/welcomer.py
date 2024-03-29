from datetime import datetime, timedelta
import random
from re import match
import re
from types import SimpleNamespace
from typing import Literal, Optional, Tuple, Union
import typing
import urllib

import discord
import d20
from urllib.request import urlopen, urlretrieve
from urllib.error import HTTPError, URLError
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

class Percent(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            if argument[-1] == '%':
                return float(argument[:-1]) / 100
            return float(argument)
        except:
            return None
        
RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

MEMBER_NAME_TOKEN = "$MEMBER_NAME$"
SERVER_NAME_TOKEN = "$SERVER_NAME$"
MEMBER_COUNT_TOKEN = "$MEMBER_COUNT$"
ACTION_TOKEN = "$ACTION$"


def replace_tokens(text, member: discord.Member, use_mentions: typing.Optional[bool] = False, token: typing.Optional[str] = None):
    if token is not None:
        return text.replace(token, )
    return text.replace(
        MEMBER_NAME_TOKEN, member.display_name if not use_mentions else member.mention
    ).replace(
        SERVER_NAME_TOKEN, member.guild.name
    ).replace(
        MEMBER_COUNT_TOKEN, str(member.guild.member_count)
    )


DEFAULT_GUILD = {
    "greeting": {
        "name": "Greeting messages",
        "channel_ids": [],
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
    "hello": {
        "name": "Hello messages",
        "enabled": True,
        "use_embed": False,
        "color": discord.Color.dark_gold().to_rgb(),
        "title": "",
        "messages": [
            f"Hello, {MEMBER_NAME_TOKEN}.",
            f"Hi, {MEMBER_NAME_TOKEN}.",
            f"Salutations, {MEMBER_NAME_TOKEN}.",
            f"Konnichiwa, {MEMBER_NAME_TOKEN}.",
            f"Hello there, {MEMBER_NAME_TOKEN}.",
            f"Shut up, {MEMBER_NAME_TOKEN}."
        ],
        "embed_image_url": "",
        "footer": "",
        "cooldown_minutes": "1d30",
        "current_cooldown": 0,
        "last_trigger_timestamp": 0,
        "chance": 0.1,
        "always_list": [
            934068329482698762
        ],
        "triggers": [
            "hello",
            "hi",
            "salutations",
            "konnichiwa"
        ]
    },
    "based": {
        "name": "Meme based responder",
        "enabled": True,
        "use_embed": False,
        "color": discord.Color.dark_gold().to_rgb(),
        "title": "",
        "messages": [
            f"Based on what?",
        ],
        "embed_image_url": "",
        "footer": "",
        "cooldown_minutes": "3d4",
        "current_cooldown": 0,
        "last_trigger_timestamp": 0,
        "chance": 1,
        "always_list": [
        ],
        "triggers": [
            "based",
            "based.",
            "based?",
            "based..."
            "...based",
            "b-based"
        ]
    },
    "gg": {
        "name": "Respond to good game messages",
        "enabled": False,
        "use_embed": False,
        "color": discord.Color.dark_gold().to_rgb(),
        "title": "",
        "messages": [
            f"There are no good games, only bad games. Keep that in mind {MEMBER_NAME_TOKEN}.",
            f"{MEMBER_NAME_TOKEN}, please use \"bgs\" or \"bad games\" instead. Consider this a warning.",
            f"User {MEMBER_NAME_TOKEN} has been warned for their misuse of post-set formalities.",
            f"You've just violated our #hisouten netplay etiquette. Please refer to <#1091515229084581939> and do not make the same mistake again. This is a warning.",
            f"This behavior is not acceptable. Please refer to <#1091515229084581939>.",
            f"{MEMBER_NAME_TOKEN}, you've used a banned phrase. Further violation will not be condoned.",
        ],
        "embed_image_url": "",
        "footer": "",
        "cooldown_minutes": "1d1 - 1",
        "current_cooldown": 0,
        "last_trigger_timestamp": 0,
        "chance": 1,
        "always_list": [
        ],
        "triggers": [
            "ggs",
            "gg",
            "good games",
            "good game",
        ]
    },
    "thanks": {
        "name": "Respond to thanks for playing messages",
        "enabled": False,
        "use_embed": False,
        "color": discord.Color.dark_gold().to_rgb(),
        "title": "",
        "messages": [
            f"{MEMBER_NAME_TOKEN} - DO NOT THANK YOUR OPPONENT FOR WASTING YOUR TIME.",
            f"{MEMBER_NAME_TOKEN}, if you have time to be thankful, you should use it insulting your opponent.",
            f"You've just violated our #hisouten netplay etiquette. Please refer to <#1091515229084581939> and do not make the same mistake again. This is a warning.",
            f"This behavior is not acceptable. Please refer to <#1091515229084581939>.",
            f"{MEMBER_NAME_TOKEN}, you've used a banned phrase. Further violation will not be condoned.",
        ],
        "embed_image_url": "",
        "footer": "",
        "cooldown_minutes": "1d1 - 1",
        "current_cooldown": 0,
        "last_trigger_timestamp": 0,
        "chance": 1,
        "always_list": [
        ],
        "triggers": [
            "thanks for playing",
            "thank you for playing",
            "ty for playing",
            "thanks for the games",
            "thank you for the games",
            "ty for the games",
        ]
    },
    "departure": {
        "name": "Departure messages",
        "channel_ids": [],
        "enabled": False,
        "use_embed": False,
        "color": discord.Color.darker_grey().to_rgb(),
        "title": "",
        "messages": [
            f"**{MEMBER_NAME_TOKEN}** has left us.  Press :regional_indicator_f: to pay respects."
        ],
        "embed_image_url": "",
        "footer": ""
    },
    "kick_or_ban": {
        "name": "Kick / Ban messages",
        "channel_ids": [],
        "enabled": False,
        "use_embed": False,
        "color": discord.Color.dark_red().to_rgb(),
        "title": "",
        "messages": [
            f"**{MEMBER_NAME_TOKEN}** was {ACTION_TOKEN}ed.  They deserved it."
        ],
        "embed_image_url": "",
        "footer": ""
    },
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
        self._ban_cache = {}

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
            raise commands.BadArgument(
                "Couldn't find the message at the given index.")

        str = obj["messages"].pop(int)
        if len(obj["messages"]) == 0:
            str += f"\n\nYou must have at least one message before {obj['name']} will fire."

        await ctx.send(f"Removed the following string to {obj['name']}:\n{str}")
        return obj
    
    async def _list_channel(self, ctx, obj):
        embed = discord.Embed()
        embed.title = f"Channels for {obj['name'].lower()}:"

        channels = []
        channel_ids = obj['channel_ids']

        for i in range(len(channel_ids)):
            try:
                channel : discord.TextChannel = await self.bot.fetch_channel(channel_ids[i])
                channels.append(f"[{i}] {channel.mention}")
            except:
                channel_ids.remove(channel_ids[i])
                continue

        embed.description = '\n'.join(channels)

        obj['channel_ids'] = sorted(channel_ids)

        await ctx.send(embed=embed)
        return obj
    
    async def _add_channel(self, ctx, obj, channel: discord.TextChannel):
        obj["channel_ids"] = list(set(obj["channel_ids"] + [channel.id]))
        await ctx.send(f"Added {channel.mention} to the {obj['name']} channel list.")
        await self._list_channel(ctx, obj)
        return obj
    
    async def _remove_channel(self, ctx, obj, channel: discord.TextChannel):
        obj["channel_ids"].discard(channel.id)
        await ctx.send(f"Removed {channel.mention} from the {obj['name']} channel list.")
        await self._list_channel(ctx, obj)
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

    async def _chance(self, ctx, obj, chance: typing.Optional[float] = None):
        if chance is not None:
            if chance <= 0 or chance > 1.0:
                await ctx.send("ERROR: Chance must be between (0, 1]")
                return

            obj["chance"] = chance

            await ctx.send(f"Set the chance to greet users to {chance * 100}%.")
        else:
            await ctx.send(f"The chance to greet users is currently {obj['chance'] * 100}%.")

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

        if "footer" in obj and obj["footer"] != "":
            embed.set_footer(text=replace_tokens(
                obj["footer"], member), icon_url=member.avatar.url)

        if "embed_image_url" in obj and obj["embed_image_url"] != "":
            embed.set_thumbnail(url=obj["embed_image_url"])

        if "action" in obj and obj["action"] != "":
            embed.description = embed.description.replace(
                ACTION_TOKEN, obj["action"]
            )
            embed.title = embed.title.replace(
                ACTION_TOKEN, obj["action"]
            )

        if "perp" in obj:
            embed.add_field(
                name=f"{obj['action'].capitalize()}ed by:", value=obj['perp'].mention, inline=True)

            if "reason" in obj and obj["reason"] != "":
                embed.add_field(
                    name="Reason:", value=obj["reason"], inline=True)

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
            return

        if obj["use_embed"]:
            return await self._create_embed(channel, obj, member)
        else:
            return await self._create_simple(channel, obj, member)

    async def _template(self, channel, obj):
        member = SimpleNamespace(**{
            "display_name": MEMBER_NAME_TOKEN,
            "guild": SimpleNamespace(**{
                "name": SERVER_NAME_TOKEN,
                "member_count": MEMBER_COUNT_TOKEN
            }),
            "avatar_url": self.bot.user.avatar.url,
            "mention": "$MEMBER_MENTION$"
        })
        return await self._create(channel, obj, member)

    @commands.group(name="welcomer")
    @commands.mod_or_permissions(manage_roles=True)
    async def settings(self, ctx: commands.Context):
        """Settings for controlling the server greeting and departure messages.
        """
        pass

    @settings.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.Context, verbose: typing.Optional[bool] = True):
        """Clears all data. WARNING: Irreversible.

        Args:
            verbose (typing.Optional[bool], optional): Verbose output. Defaults to True.
        """
        guild: discord.Guild = ctx.guild
        await self.config.guild(guild).clear()
        if verbose:
            await ctx.send(f"Data cleared for {guild.name}.")

    
    @settings.command()
    @commands.is_owner()
    async def clear_specific(self, ctx: commands.Context, config_type: str, verbose: typing.Optional[bool] = True):
        """Clears specific data for a config. WARNING: Irreversible.

        Args:
            config (str): The type of config to clear.
        """
        config_type = config_type.lower()

        if config_type not in DEFAULT_GUILD.keys():
            await ctx.send(f"Invalid config type provided, please choose from: `{DEFAULT_GUILD.keys()}`")
            return
        
        guild: discord.Guild = ctx.guild
        config = DEFAULT_GUILD[config_type]
        await self.config.guild(guild).get_attr(config_type).set(config)
        if verbose:
            await ctx.send(f"Data reset for {config_type} in {guild.name}.")

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

    @greeting.group(name="channel")
    async def greeting_channel(self, ctx: commands.Context):
        """Sets or displays the current channel for greeting announcements.
        """
        return
    
    
    @greeting_channel.command(name='list')
    async def greeting_channel_list(self, ctx: commands.Context):
        """Lists the current channels for this module.

        Args:
            ctx (commands.Context): _description_
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        await self._list_channel(ctx, greeting)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass
        
    @greeting_channel.command(name='add')
    async def greeting_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """Adds a channel to the channel list when sending greeting messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to add.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        await self._add_channel(ctx, greeting, channel)
        await self.config.guild(ctx.guild).greeting.set(greeting)
        pass
        
    @greeting_channel.command(name='remove')
    async def greeting_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Removes a channel from the channel list when sending greeting messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to remove.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        await self._remove_channel(ctx, greeting, channel)
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

    @greeting.command(name="template")
    async def greeting_template(self, ctx: commands.Context):
        """Generates a template of what the greeting message will look like.
        """
        greeting = await self.config.guild(ctx.guild).greeting()
        await self._template(ctx.channel, greeting)
        pass

    @settings.group()
    async def hello(self, ctx: commands.Context):
        """Commands for configuring the server hello messages.
        """
        pass

    @hello.command(name="toggle")
    async def hello_toggle(self, ctx: commands.Context):
        """Toggles the hello functionality for the bot.
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._toggle(ctx, hello)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="enable")
    async def hello_enable(self, ctx: commands.Context):
        """Enables hello messages for the server.
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._enable(ctx, hello)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="disable")
    async def hello_disable(self, ctx: commands.Context):
        """Disables hello messages for the server.
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._disable(ctx, hello)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="enabled")
    async def hello_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of hello messages for the server.

        Args:
            bool (bool): (Optional) True / False
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._enabled(ctx, hello, bool)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass


    @hello.command(name="list")
    async def hello_list(self, ctx: commands.Context):
        """Gets the list of random hello messages for the server.
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._list(ctx, hello)
        pass

    @hello.command(name="add", help=f"""Adds a new hello message for use in the server.  Use the following escaped strings for values:
        -- ``{MEMBER_NAME_TOKEN}`` - The target member's name
        -- ``{SERVER_NAME_TOKEN}`` - The server name
        -- ``{MEMBER_COUNT_TOKEN}`` - The server member count

        Args:
        \t\tentry (str): The new hello message to be used at random.
        """)
    async def hello_add(self, ctx: commands.Context, *, entry: str):
        """Adds a new hello message for use in the server.

        Args:
            entry (str): The new hello message to be used at random.
        """
        entry = entry.strip("\"\'")
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._add(ctx, hello, entry)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="remove")
    async def hello_remove(self, ctx: commands.Context, index: int):
        """Removes a hello message for use in the server.

        Args:
            index (int): The index of the hello message to remove (use `welcomer hello list` to verify the correct index).
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._remove(ctx, hello, index)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="useembed")
    async def hello_use_embed(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets hello message type to Embeds or Simple.

        Args:
            bool (bool): (Optional) True / False
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._use_embed(ctx, hello, bool)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="image", aliases=["thumbnail"])
    async def hello_image(self, ctx: commands.Context, *, url: typing.Optional[str] = None):
        """Sets the hello message image thumbnail used in Rich Embed hello messages.

        Args:
            url (str): (Optional) A valid URL to the thumbnail image desired.
        """
        if url is not None:
            url = url.strip("\"\'")
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._image(ctx, hello, url)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="title")
    async def hello_title(self, ctx: commands.Context, *, title: typing.Optional[str] = None):
        """Sets the hello message title used in Rich Embed hello messages.

        Args:
            title (str): (Optional) The title string to use in hello messages.
        """
        if title is not None:
            title = title.strip("\"\'")
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._title(ctx, hello, title)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="footer")
    async def hello_footer(self, ctx: commands.Context, *, footer: typing.Optional[str] = None):
        """Sets the hello message footer used in Rich Embed hello messages.

        Args:
            title (str): (Optional) The footer string to use in hello messages.
        """
        if footer is not None:
            footer = footer.strip("\"\'")
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._footer(ctx, hello, footer)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.command(name="template")
    async def hello_template(self, ctx: commands.Context):
        """Generates a template of what the hello message will look like.
        """
        hello = await self.config.guild(ctx.guild).hello()
        await self._template(ctx.channel, hello)
        pass

    @hello.command(name="cooldown")
    async def hello_cooldown(self, ctx: commands.Context, *, cooldown: typing.Optional[str]):
        """Sets the cooldown used by the greeter.

        Args:
            cooldown (str): The cooldown amount; either a number or an RNG dice amount (1d30 for random within 30 minutes).
        """
        hello = await self.config.guild(ctx.guild).hello()

        if cooldown is not None:
            try:
                parsed = d20.parse(cooldown)
            except d20.RollSyntaxError as e:
                await ctx.send("ERROR: Please enter a valid cooldown using dice notation or a number.")
                return

            hello["cooldown_minutes"] = cooldown

            # Moving the cooldown to whatever the new amount is.
            if hello["current_cooldown"] > datetime.now().timestamp():
                hello["current_cooldown"] = (datetime.fromtimestamp(
                    hello["last_trigger_timestamp"]) + timedelta(minutes=d20.roll(cooldown).total)).timestamp()

            await self.config.guild(ctx.guild).hello.set(hello)

            await ctx.send(f"Set the cooldown to greet users to {cooldown} minutes.")
        else:
            await ctx.send(f"The chance to greet users is currently {hello['cooldown_minutes']} minutes.")
        pass

    @hello.command(name="chance")
    async def hello_chance(self, ctx: commands.Context, *, chance: typing.Optional[Percent]):
        """Sets the random chance that the greeter will go off.

        Args:
            chance (float): A number between 0.00 and 1.00
        """
        hello = await self.config.guild(ctx.guild).hello()
        hello = await self._chance(ctx, hello, chance)
        await self.config.guild(ctx.guild).hello.set(hello)
        pass

    @hello.group(name="always")
    async def hello_always(self, ctx: commands.Context):
        """Sets the list of users who will always receive hello messages.
        """
        pass

    @hello_always.command(name="list")
    async def hello_always_list(self, ctx: commands.Context):
        """Gets the list of random hello messages for the server.
        """
        hello = await self.config.guild(ctx.guild).hello()
        always_list = hello["always_list"]
        guild: discord.Guild = ctx.guild
        embed = discord.Embed()
        embed.title = "Forced to greet the following users:"

        users = []

        for i in range(len(always_list)):
            member: discord.Member = guild.get_member(always_list[i])

            if member is None:
                continue

            users.append(f"[{i}] {member.mention}")

        embed.description = '\n'.join(users)

        await ctx.send(embed=embed)
        pass

    @hello_always.command(name="add")
    async def hello_always_add(self, ctx: commands.Context, *, member: discord.Member):
        """Adds a user to always have hello messages sent to them.

        Args:
            member (discord.Member): The member to always greet.
        """
        hello = await self.config.guild(ctx.guild).hello()

        if member.id in hello["always_list"]:
            await ctx.send(f"{member.display_name} is already on the always-greet list.")
            return

        hello["always_list"].append(member.id)
        await self.config.guild(ctx.guild).hello.set(hello)
        await ctx.send(f"Added user {member.display_name} to the list of always-greeted members.")
        pass

    @hello_always.command(name="remove")
    async def hello_always_remove(self, ctx: commands.Context, *, member: discord.Member):
        """Removes a user from always being greeted.

        Args:
            member (discord.Member): The member to remove.
        """
        hello = await self.config.guild(ctx.guild).hello()

        if member.id not in hello["always_list"]:
            await ctx.send(f"{member.display_name} is not on the always-greet list.")
            return

        hello["always_list"].remove(member.id)
        await self.config.guild(ctx.guild).hello.set(hello)
        await ctx.send(f"Removed {member.display_name} from the list of always-greeted members.")
        pass

    @hello.group(name="triggers")
    async def hello_triggers(self, ctx: commands.Context):
        """Sets the list of trigger phrases to generate hello messages.
        """
        pass

    @hello_triggers.command(name="list")
    async def hello_triggers_list(self, ctx: commands.Context):
        """Gets the list of random hello messages for the server.
        """
        hello = await self.config.guild(ctx.guild).hello()
        triggers = hello["triggers"]
        guild: discord.Guild = ctx.guild
        embed = discord.Embed()
        embed.title = "Hello Trigger Phrases:"

        phrases = []

        for i in range(len(triggers)):
            phrase = triggers[i]

            phrases.append(f"[{i}] {phrase}")

        embed.description = '\n'.join(phrases)

        await ctx.send(embed=embed)
        pass

    @hello_triggers.command(name="add")
    async def hello_triggers_add(self, ctx: commands.Context, *, phrase: str):
        """Adds a phrase which will trigger Hello messages.

        Args:
            phrase (str): The phrase to add for triggering.
        """
        hello = await self.config.guild(ctx.guild).hello()

        if phrase.lower() in hello["triggers"]:
            await ctx.send(f"``{phrase}`` is already triggering hello phrases.")
            return

        hello["triggers"].append(phrase.lower())
        await self.config.guild(ctx.guild).hello.set(hello)
        await ctx.send(f"Added ``{phrase}`` to the list of hello triggers.")
        pass

    @hello_triggers.command(name="remove")
    async def hello_triggers_remove(self, ctx: commands.Context, *, phrase: str):
        """Removes a phrase from triggering hello messages.

        Args:
            phrase (str | int): The triggering phrase.
        """
        hello = await self.config.guild(ctx.guild).hello()

        try:
            phrase = int(phrase)

            if phrase >= len(hello["triggers"]):
                await ctx.send(f"``{phrase}`` is out of range.")
                return
            
            removed_phrase = hello["triggers"].pop(phrase)
        
        except:
            if phrase.lower() not in hello["triggers"]:
                await ctx.send(f"``{phrase}`` is not on the triggers list.")
                return

            removed_phrase = hello["triggers"].remove(phrase.lower())
        
        await self.config.guild(ctx.guild).hello.set(hello)
        await ctx.send(f"Removed ``{removed_phrase}`` to the list of triggers for hello messages.")
        pass

    ########################## BASED ###############################

    @settings.group()
    async def based(self, ctx: commands.Context):
        """Commands for configuring the based departure messages.
        """
        pass

    @based.command(name="enable")
    async def based_enable(self, ctx: commands.Context):
        """Enables based messages for the server.
        """
        based = await self.config.guild(ctx.guild).based()
        based = await self._enable(ctx, based)
        await self.config.guild(ctx.guild).based.set(based)
        pass

    @based.command(name="disable")
    async def based_disable(self, ctx: commands.Context):
        """Disables based messages for the server.
        """
        based = await self.config.guild(ctx.guild).based()
        based = await self._disable(ctx, based)
        await self.config.guild(ctx.guild).based.set(based)
        pass

    @based.command(name="enabled")
    async def based_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of based messages for the server.

        Args:
            bool (bool): (Optional) True / False
        """
        based = await self.config.guild(ctx.guild).based()
        based = await self._enabled(ctx, based, bool)
        await self.config.guild(ctx.guild).based.set(based)
        pass

    

    @based.command(name="cooldown")
    async def based_cooldown(self, ctx: commands.Context, *, cooldown: typing.Optional[str]):
        """Sets the cooldown used by the 'based' meme responder.

        Args:
            cooldown (str): The cooldown amount; either a number or an RNG dice amount (1d30 for random within 30 minutes).
        """
        based = await self.config.guild(ctx.guild).based()

        if cooldown is not None:
            try:
                parsed = d20.parse(cooldown)
            except d20.RollSyntaxError as e:
                await ctx.send("ERROR: Please enter a valid cooldown using dice notation or a number.")
                return

            based["cooldown_minutes"] = cooldown

            # Moving the cooldown to whatever the new amount is.
            if based["current_cooldown"] > datetime.now().timestamp():
                based["current_cooldown"] = (datetime.fromtimestamp(
                    based["last_trigger_timestamp"]) + timedelta(minutes=d20.roll(cooldown).total)).timestamp()

            await self.config.guild(ctx.guild).based.set(based)

            await ctx.send(f"Set the cooldown to meme users to {cooldown} minutes.")
        else:
            await ctx.send(f"The chance to meme users is currently {based['cooldown_minutes']} minutes.")
        pass

    ####################################################################

    ##########################   GG   ###############################

    @settings.group()
    async def gg(self, ctx: commands.Context):
        """Commands for configuring the good games messages.
        """
        pass

    @gg.command(name="enable")
    async def gg_enable(self, ctx: commands.Context):
        """Enables good games messages for the server.
        """
        gg = await self.config.guild(ctx.guild).gg()
        gg = await self._enable(ctx, gg)
        await self.config.guild(ctx.guild).gg.set(gg)
        pass

    @gg.command(name="disable")
    async def gg_disable(self, ctx: commands.Context):
        """Disables good games messages for the server.
        """
        gg = await self.config.guild(ctx.guild).gg()
        gg = await self._disable(ctx, gg)
        await self.config.guild(ctx.guild).gg.set(gg)
        pass

    @gg.command(name="enabled")
    async def gg_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of good games messages for the server.

        Args:
            bool (bool): (Optional) True / False
        """
        gg = await self.config.guild(ctx.guild).gg()
        gg = await self._enabled(ctx, gg, bool)
        await self.config.guild(ctx.guild).gg.set(gg)
        pass

    ####################################################################

    ########################## THANKS ###############################

    @settings.group(aliases=["ty"])
    async def thanks(self, ctx: commands.Context):
        """Commands for configuring the thanks departure messages.
        """
        pass

    @thanks.command(name="enable")
    async def thanks_enable(self, ctx: commands.Context):
        """Enables thanks messages for the server.
        """
        thanks = await self.config.guild(ctx.guild).thanks()
        thanks = await self._enable(ctx, thanks)
        await self.config.guild(ctx.guild).thanks.set(thanks)
        pass

    @thanks.command(name="disable")
    async def thanks_disable(self, ctx: commands.Context):
        """Disables thanks messages for the server.
        """
        thanks = await self.config.guild(ctx.guild).thanks()
        thanks = await self._disable(ctx, thanks)
        await self.config.guild(ctx.guild).thanks.set(thanks)
        pass

    @thanks.command(name="enabled")
    async def thanks_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of thanks messages for the server.

        Args:
            bool (bool): (Optional) True / False
        """
        thanks = await self.config.guild(ctx.guild).thanks()
        thanks = await self._enabled(ctx, thanks, bool)
        await self.config.guild(ctx.guild).thanks.set(thanks)
        pass

    ####################################################################

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

    @departure.group(name="channel")
    async def departure_channel(self, ctx: commands.Context):
        """Sets or displays the current channel for departure announcements.
        """
        return
    
    @departure_channel.command(name='list')
    async def departure_channel_list(self, ctx: commands.Context):
        """Lists the current channels for this module.

        Args:
            ctx (commands.Context): _description_
        """
        departure = await self.config.guild(ctx.guild).departure()
        await self._list_channel(ctx, departure)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass
        
    @departure_channel.command(name='add')
    async def departure_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """Adds a channel to the channel list when sending departure messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to add.
        """
        departure = await self.config.guild(ctx.guild).departure()
        await self._add_channel(ctx, departure, channel)
        await self.config.guild(ctx.guild).departure.set(departure)
        pass
        
    @departure_channel.command(name='remove')
    async def departure_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Removes a channel from the channel list when sending departure messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to remove.
        """
        departure = await self.config.guild(ctx.guild).departure()
        await self._remove_channel(ctx, departure, channel)
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
        \t\tentry (str): The new departure message to be used at random.
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

    @departure.command(name="template")
    async def departure_template(self, ctx: commands.Context):
        """Generates a template of what the departure message will look like.
        """
        departure = await self.config.guild(ctx.guild).departure()
        await self._template(ctx.channel, departure)
        pass

    @settings.group(aliases=["ban"])
    async def kick(self, ctx: commands.Context):
        """Commands for configuring the server departure messages.
        """
        pass

    @kick.command(name="toggle")
    async def kick_toggle(self, ctx: commands.Context):
        """Toggles the kick / ban message functionality for the bot.
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._toggle(ctx, kick_or_ban)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="enable")
    async def kick_enable(self, ctx: commands.Context):
        """Enables kick / ban messages for the server.
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._enable(ctx, kick_or_ban)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="disable")
    async def kick_disable(self, ctx: commands.Context):
        """Disables kick / ban messages for the server.
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._disable(ctx, kick_or_ban)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="enabled")
    async def kick_enabled(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets or shows the status of kick / ban messages for the server.

        Args:
            bool (bool): (Optional) True / False
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._enabled(ctx, kick_or_ban, bool)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.group(name="channel")
    async def kick_channel(self, ctx: commands.Context):
        """Sets or displays the current channel for kick announcements.
        """
        return
    
    
    @kick_channel.command(name='list')
    async def kick_channel_list(self, ctx: commands.Context):
        """Lists the current channels for this module.

        Args:
            ctx (commands.Context): _description_
        """
        kick = await self.config.guild(ctx.guild).kick_or_ban()
        await self._list_channel(ctx, kick)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick)
        pass
        
    @kick_channel.command(name='add')
    async def kick_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """Adds a channel to the channel list when sending kick messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to add.
        """
        kick = await self.config.guild(ctx.guild).kick_or_ban()
        await self._add_channel(ctx, kick, channel)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick)
        pass
        
    @kick_channel.command(name='remove')
    async def kick_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Removes a channel from the channel list when sending kick messages.

        Args:
            ctx (commands.Context): Command context
            channel (discord.TextChannel): The channel to remove.
        """
        kick = await self.config.guild(ctx.guild).kick_or_ban()
        await self._remove_channel(ctx, kick, channel)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick)
        pass

    @kick.command(name="list")
    async def kick_list(self, ctx: commands.Context):
        """Gets the list of random kick / ban messages for the server.
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._list(ctx, kick_or_ban)
        pass

    @kick.command(name="add", help=f"""Adds a new kick / ban message for use in the server.  Use the following escaped strings for values:
        -- ``{MEMBER_NAME_TOKEN}`` - The target member's name
        -- ``{SERVER_NAME_TOKEN}`` - The server name
        -- ``{MEMBER_COUNT_TOKEN}`` - The server member count

        Args:
        \t\tentry (str): The new kick / ban message to be used at random.
        """)
    async def kick_add(self, ctx: commands.Context, *, entry: str):
        """Adds a new kick / ban message for use in the server.

        Args:
            entry (str): The new kick / ban message to be used at random.
        """
        entry = entry.strip("\"\'")
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._add(ctx, kick_or_ban, entry)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="remove")
    async def kick_remove(self, ctx: commands.Context, index: int):
        """Removes a kick / ban message for use in the server.

        Args:
            index (int): The index of the kick / ban message to remove (use `welcomer kick list` to verify the correct index).
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._remove(ctx, kick_or_ban, index)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="useembed")
    async def kick_use_embed(self, ctx: commands.Context, bool: typing.Optional[bool] = None):
        """Sets kick / ban message type to Embeds or Simple.

        Args:
            bool (bool): (Optional) True / False
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._use_embed(ctx, kick_or_ban, bool)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="image", aliases=["thumbnail"])
    async def kick_image(self, ctx: commands.Context, *, url: typing.Optional[str] = None):
        """Sets the kick / ban message image thumbnail used in Rich Embed kick / ban messages.

        Args:
            url (str): (Optional) A valid URL to the thumbnail image desired.
        """
        if url is not None:
            url = url.strip("\"\'")
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._image(ctx, kick_or_ban, url)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="title")
    async def kick_title(self, ctx: commands.Context, *, title: typing.Optional[str] = None):
        """Sets the kick / ban message title used in Rich Embed kick / ban messages.

        Args:
            title (str): (Optional) The title string to use in kick / ban messages.
        """
        if title is not None:
            title = title.strip("\"\'")
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._title(ctx, kick_or_ban, title)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="footer")
    async def kick_footer(self, ctx: commands.Context, *, footer: typing.Optional[str] = None):
        """Sets the kick / ban message footer used in Rich Embed kick / ban messages.

        Args:
            title (str): (Optional) The footer string to use in kick / ban messages.
        """
        if footer is not None:
            footer = footer.strip("\"\'")
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban = await self._footer(ctx, kick_or_ban, footer)
        await self.config.guild(ctx.guild).kick_or_ban.set(kick_or_ban)
        pass

    @kick.command(name="template")
    async def kick_template(self, ctx: commands.Context):
        """Generates a template of what the kick / ban message will look like.
        """
        kick_or_ban = await self.config.guild(ctx.guild).kick_or_ban()
        kick_or_ban["action"] = "kick"
        kick_or_ban["perp"] = ctx.bot.user
        kick_or_ban["reason"] = "Reason for kicking."
        await self._template(ctx.channel, kick_or_ban)
        pass

    async def create_if_enabled(self, member: discord.Member, obj):
        guild = member.guild

        if obj["enabled"]:
            channel_ids = obj['channel_ids']
            for channel_id in channel_ids:
                channel = guild.get_channel(channel_id)

                if channel is not None:
                    await self._create(channel, obj, member)

    async def get_audit_log_reason(
        self,
        guild: discord.Guild,
        target: Union[discord.abc.GuildChannel, discord.Member, discord.Role],
        action: discord.AuditLogAction,
    ) -> Tuple[Optional[discord.abc.User], Optional[str]]:
        perp = None
        reason = None
        if guild.me.guild_permissions.view_audit_log:
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == target.id and (
                    log.created_at > (
                        datetime.now(tz=pytz.timezone("UTC")) - timedelta(0, 5))
                ):
                    perp = log.user
                    if log.reason:
                        reason = log.reason
                    break
        return perp, reason

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires greeting messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """
        if member.bot:
            return

        if member.id == 386960058636042245:
            return

        greeting = await self.config.guild(member.guild).greeting()

        await self.create_if_enabled(member, greeting)

        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Fires departure or kick / ban messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """
        if member.bot:
            return

        if member.id == 386960058636042245:
            return

        guild = member.guild

        if guild.id in self._ban_cache and member.id in self._ban_cache[guild.id]:
            perp, reason = await self.get_audit_log_reason(
                guild, member, discord.AuditLogAction.ban
            )
        else:
            perp, reason = await self.get_audit_log_reason(
                guild, member, discord.AuditLogAction.kick
            )

        if perp is not None:
            kick_or_ban = await self.config.guild(guild).kick_or_ban()
            kick_or_ban["perp"] = perp
            kick_or_ban["reason"] = reason

            if guild.id in self._ban_cache and member.id in self._ban_cache[guild.id]:
                kick_or_ban["action"] = 'ban'
                pass
            else:
                kick_or_ban["action"] = 'kick'
                pass

            await self.create_if_enabled(member, kick_or_ban)
            return

        departure = await self.config.guild(guild).departure()

        await self.create_if_enabled(member, departure)

        pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member):
        """
        This is only used to track that the user was banned and not kicked/removed
        """
        if guild.id not in self._ban_cache:
            self._ban_cache[guild.id] = [member.id]
        else:
            self._ban_cache[guild.id].append(member.id)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, member: discord.Member):
        """
        This is only used to track that the user was banned and not kicked/removed
        """
        if guild.id in self._ban_cache:
            if member.id in self._ban_cache[guild.id]:
                self._ban_cache[guild.id].remove(member.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for hello triggers and rolls a chance to trigger a response.

        Args:
            message (discord.Message): The discord message listened to.
        """
        if message.author.bot:
            return

        if message.author.id == 386960058636042245:
            return

        prefix = await self.bot.get_prefix(message)

        if isinstance(prefix, str):
            if message.content.startswith(prefix):
                return
        else:
            if any(message.content.startswith(p) for p in prefix):
                return

        hello = await self.config.guild(message.guild).hello()

        if hello["enabled"]:
            content = message.content.lower().split()
            if any([
                t in content and
                content.index(t) > -1
                for t in hello["triggers"]
            ]):
                if (
                    message.author.id in hello["always_list"] and
                    (datetime.now() - timedelta(minutes=1)
                     ).timestamp() > hello["last_trigger_timestamp"]
                ):
                    is_firing = True
                else:
                    is_firing = (
                        random.random() < hello["chance"] and
                        datetime.now().timestamp() > hello["current_cooldown"]
                    )

                if is_firing:
                    await self._create(message.channel, hello, message.author)
                    hello["current_cooldown"] = (datetime.now(
                    ) + timedelta(minutes=d20.roll(hello["cooldown_minutes"]).total)).timestamp()
                    hello["last_trigger_timestamp"] = datetime.now().timestamp()
                    await self.config.guild(message.guild).hello.set(hello)

        meme_checks = {
            "based": await self.config.guild(message.guild).based(),
            "gg": await self.config.guild(message.guild).gg(),
            "thanks": await self.config.guild(message.guild).thanks(),
        }

        for key, config in meme_checks.items():
            if config["enabled"]:
                content: str = message.content.lower()
                if (
                    (
                        any([
                            word for word in content.split()
                            if word in config["triggers"]
                        ]) and len(content.split()) < 6
                    ) or
                        any([
                            t in content and
                            (
                                content.find(t) == 0 or
                                (
                                    content.find(t) > -1 and
                                    content[content.find(t) - 1] in [' ', '\n', '\t', ',', '.']
                                )
                            )
                            for t in config["triggers"]
                        ])
                ):
                    if key == "gg" or key == "thanks":
                        if random.random() < 0.05:  # 5% chance to trigger a special message.
                            await message.reply(f"`[WARNING]` This is your final warning, {message.author.mention}.")
                            return
                    if key == 'based':
                        if len(content.split()) > 6 or content.find("based on") > -1 or content.find("based of") > -1 or content.find("based at") > -1:
                            continue

                    if (
                        message.author.id in config["always_list"] and
                        (datetime.now() - timedelta(minutes=1)
                         ).timestamp() > config["last_trigger_timestamp"]
                    ):
                        is_firing = True
                    else:
                        is_firing = (
                            random.random() < config["chance"] and
                            datetime.now().timestamp(
                            ) > config["current_cooldown"]
                        )

                    if is_firing:
                        await self._create(message.channel, config, message.author)
                        config["current_cooldown"] = (datetime.now(
                        ) + timedelta(minutes=d20.roll(config["cooldown_minutes"]).total)).timestamp()
                        config["last_trigger_timestamp"] = datetime.now().timestamp()
                        await self.config.guild(message.guild).get_attr(key).set(config)
                        return
        pass
