import datetime
import random
import re
import typing

import discord
import d20
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from utils.converters.percent import Percent

from utils.tokenizer import MEMBER_NAME_TOKEN, replace_tokens, to_percent

RequestType = typing.Literal["discord_deleted_user",
                             "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "enabled": True,
    "reasons": [
        f"Shut up, {MEMBER_NAME_TOKEN}.",
        f"Fuck you, {MEMBER_NAME_TOKEN}.",
        f"Don't be rude.",
        f"Heresy.",
        f"Punk.",
        f"j.2a",
    ],
    "cooldown_minutes": "1d30",
    "cooldown_timestamp": 0,
    "chance": 0.1,
    "timeout_mins": 0,
    "always_list": [

    ],
    "triggers": [
        "shut up remi",
        "fuck you remi",
        "f u remi",
        "fu remi",
        "shut it remi",
        "shuddup remi",
        "shaddup remi",
        "quiet remi",
    ]
}


class Bully(commands.Cog):
    """
    Bully users who upset the bot.
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

    @commands.hybrid_group()
    @commands.mod_or_permissions(manage_channels=True)
    async def bully(self, ctx: commands.Context):
        """Commands for bullying users who upset the bot.

        Args:
            ctx (commands.Context): Command context.
        """
        pass

    @bully.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Enable or disable this functionality.

        Args:
            ctx (commands.Context): Command context.
            bool (typing.Optional[bool]): Whether to enable or disable it.
        """
        if not bool:
            bool = await self.config.guild(ctx.guild).enabled()

        if bool:
            status_msg = "**ENABLED**"
        else:
            status_msg = "**DISABLED**"

        await ctx.send(f"Bullying is currently {status_msg}.")

        await self.config.guild(ctx.guild).enabled.set(bool)
        pass

    @bully.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def timeout(self, ctx: commands.Context, timeout: typing.Optional[float]):
        """Sets a timeout value for kicking users for a durationi.

        Args:
            ctx (commands.Context): Command context.
            timeout (typing.Optional[float]): How long to kick someone for.
        """
        if not timeout:
            timeout = await self.config.guild(ctx.guild).timeout_mins()

        if timeout <= 0:
            timeout = 0
            await ctx.send("Currently not timing out users (only kicking).")
        else:
            await ctx.send(f"Currently timing out users for {timeout} minutes.")

        await self.config.guild(ctx.guild).timeout_mins.set(timeout)
        pass

    @bully.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def cooldown(self, ctx: commands.Context, *, minutes: typing.Optional[str]):
        """Sets the cooldown for triggering bully responses.

        Args:
            ctx (commands.Context): Command context.
            minutes (typing.Optional[str]): (d20 Notation) The cooldown in minutes.
        """
        if minutes is not None:
            try:
                parsed = d20.parse(minutes)
            except d20.RollSyntaxError as e:
                await ctx.send("ERROR: Please enter a valid cooldown using dice notation or a number.")
                return

            current_cooldown = await self.config.guild(ctx.guild).cooldown_timestamp()

            # Moving the cooldown to whatever the new amount is.
            if current_cooldown > datetime.datetime.now().timestamp():
                current_cooldown = (datetime.datetime.now() + datetime.timedelta(minutes=d20.roll(minutes).total)).timestamp()

            await self.config.guild(ctx.guild).cooldown_timestamp.set(current_cooldown)
            await self.config.guild(ctx.guild).cooldown_minutes.set(minutes)

            await ctx.send(f"Set the cooldown to greet users to {minutes} minutes.")
        else:
            await ctx.send(f"The chance to greet users is currently {await self.config.guild(ctx.guild).cooldown_minutes()} minutes.")
        pass
    

    @bully.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def chance(self, ctx: commands.Context, chance: typing.Optional[Percent]):
        """Sets the random chance that the greeter will go off.

        Args:
            chance (float): A number between 0.00 and 1.00
        """
        if chance is not None:
            if chance <= 0 or chance > 1.0:
                await ctx.send("ERROR: Chance must be between (0, 1]")
                return

            await self.config.guild(ctx.guild).chance.set(chance)

            await ctx.send(f"Set the chance to bully users to {chance * 100}%.")
        else:
            await ctx.send(f"The chance to bully users is currently {await self.config.guild(ctx.guild).chance() * 100}%.")
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for messages to bully users over.

        Args:
            message (discord.Message): The incoming message.
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

        config = self.config.guild(message.guild)

        if await config.enabled():
            content = message.content.lower()
            content = re.sub("[^a-z0-9]", "", message.content.lower())
            triggers = await config.triggers()
            triggers = [re.sub("[^a-z0-9]", "", t) for t in triggers]
            if any([
                t in content and
                content.index(t) > -1
                for t in triggers
            ]):
                always_list = await config.always_list()
                cooldown_timestamp = await config.cooldown_timestamp()
                is_firing = False
                if datetime.datetime.now().timestamp() > cooldown_timestamp:
                    if message.author.id in always_list:
                        is_firing = True
                    else:
                        chance = await config.chance()
                        is_firing = random.random() < chance

                if is_firing:
                    # Kick User
                    reasons = await config.reasons()
                    reason = replace_tokens(random.choice(
                        reasons), member=message.author, use_mentions=True)

                    timeout = await config.timeout_mins()

                    try:
                        if timeout > 0:
                            await message.author.timeout(datetime.timedelta(minutes=timeout), reason=reason)
                            await message.reply(reason)
                        else:
                            await message.author.kick(reason=reason)
                    except Exception as e:
                        await message.reply(reason)
                    pass

                    cooldown_minutes = await config.cooldown_minutes()

                    await config.cooldown_timestamp.set((datetime.datetime.now() + datetime.timedelta(minutes=d20.roll(cooldown_minutes).total)).timestamp())
