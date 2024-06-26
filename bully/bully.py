import datetime
import random
import re
import typing

import discord
import d20
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
        
MEMBER_NAME_TOKEN = "$MEMBER_NAME$"
SERVER_NAME_TOKEN = "$SERVER_NAME$"
MEMBER_COUNT_TOKEN = "$MEMBER_COUNT$"
ACTION_TOKEN = "$ACTION$"

TRIGGER_REGEX = r"[^a-z0-9\s@<>#]"


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

RequestType = typing.Literal["discord_deleted_user",
                             "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "enabled": True,
    "responses": [
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

    @bully.group(name="always")
    @commands.mod_or_permissions(manage_channels=True)
    async def always(self, ctx: commands.Context):
        """Sets the list of users who will always be bullied.
        """
        pass

    @always.command(name="list")
    @commands.mod_or_permissions(manage_channels=True)
    async def always_list(self, ctx: commands.Context):
        """Gets the list of always bullied users for the server.
        """
        always_list = await self.config.guild(ctx.guild).always_list()
        guild: discord.Guild = ctx.guild
        embed = discord.Embed()
        embed.title = "Forced to bully the following users:"

        users = []

        for i in range(len(always_list)):
            member: discord.Member = guild.get_member(always_list[i])

            if member is None:
                continue

            users.append(f"[{i}] {member.mention}")

        embed.description = '\n'.join(users)

        await ctx.send(embed=embed)
        pass

    @always.command(name="add")
    @commands.mod_or_permissions(manage_channels=True)
    async def always_add(self, ctx: commands.Context, *, member: discord.Member):
        """Adds a user to always be bullied by the bot.

        Args:
            member (discord.Member): The member to always bully.
        """
        always_list = await self.config.guild(ctx.guild).always_list()

        if member.id in always_list:
            await ctx.send(f"{member.display_name} is already on the always-bully list.")
            return

        always_list.append(member.id)
        await self.config.guild(ctx.guild).always_list.set(always_list)
        await ctx.send(f"Added user {member.display_name} to the list of always-bullied members.")
        pass

    @always.command(name="remove")
    @commands.mod_or_permissions(manage_channels=True)
    async def always_remove(self, ctx: commands.Context, *, member: discord.Member):
        """Removes a user from always being bullied.

        Args:
            member (discord.Member): The member to remove.
        """
        always_list = await self.config.guild(ctx.guild).always_list()

        if member.id not in always_list:
            await ctx.send(f"{member.display_name} is not on the always-bully list.")
            return

        always_list.remove(member.id)
        await self.config.guild(ctx.guild).always_list.set(always_list)
        await ctx.send(f"Removed {member.display_name} from the list of always-bullied members.")
        pass

    @bully.group(name="triggers")
    @commands.mod_or_permissions(manage_channels=True)
    async def triggers(self, ctx: commands.Context):
        """Sets the list of trigger phrases to generate bully responses.
        """
        pass

    @triggers.command(name="list")
    @commands.mod_or_permissions(manage_channels=True)
    async def triggers_list(self, ctx: commands.Context):
        """Gets the list of random bully messages for the server.
        """
        triggers = await self.config.guild(ctx.guild).triggers()
        embed = discord.Embed()
        embed.title = "Bully Trigger Phrases:"

        phrases = []

        for i in range(len(triggers)):
            phrase = triggers[i]

            phrases.append(f"[{i}] {phrase}")

        embed.description = '\n'.join(phrases)

        await ctx.send(embed=embed)
        pass

    @triggers.command(name="add")
    @commands.mod_or_permissions(manage_channels=True)
    async def triggers_add(self, ctx: commands.Context, *, phrase: str):
        """Adds a phrase which will trigger bully responses.

        Args:
            phrase (str): The phrase to add for triggering.  Strips out non-alphanumeric characters. 
        """
        triggers = await self.config.guild(ctx.guild).triggers()

        if phrase.lower() in triggers:
            await ctx.send(f"``{phrase}`` is already triggering bully responses.")
            return
        
        phrase = re.sub(TRIGGER_REGEX, "", phrase.lower(), flags=re.M)

        triggers.append(phrase)

        await self.config.guild(ctx.guild).triggers.set(triggers)

        await ctx.send(f"Added ``{phrase}`` to the list of bully triggers.")
        pass

    @triggers.command(name="remove")
    @commands.mod_or_permissions(manage_channels=True)
    async def triggers_remove(self, ctx: commands.Context, *, phrase: str):
        """Removes a phrase from bully triggering.

        Args:
            phrase (str | int): The triggering phrase.
        """
        triggers = await self.config.guild(ctx.guild).triggers()

        try:
            phrase = int(phrase)

            if phrase >= len(triggers):
                await ctx.send(f"``{phrase}`` is out of range.")
                return
            
            removed_phrase = triggers.pop(phrase)
        
        except:
            phrase = re.sub(TRIGGER_REGEX, "", phrase.lower())
            if phrase not in triggers:
                await ctx.send(f"``{phrase}`` is not on the triggers list.")
                return

            removed_phrase = triggers.remove(phrase)
        
        await self.config.guild(ctx.guild).triggers.set(triggers)
        await ctx.send(f"Removed ``{removed_phrase}`` to the list of triggers for bully responses.")
        pass

    @bully.group(name="responses")
    @commands.mod_or_permissions(manage_channels=True)
    async def responses(self, ctx: commands.Context):
        """Sets the list of responses for bullying users.
        """
        pass

    @responses.command(name="list")
    @commands.mod_or_permissions(manage_channels=True)
    async def responses_list(self, ctx: commands.Context):
        """Gets the list of random bully responses for the server.
        """
        responses = await self.config.guild(ctx.guild).responses()
        embed = discord.Embed()
        embed.title = "Bully Response Messages:"

        phrases = []

        for i in range(len(responses)):
            phrase = responses[i]

            phrases.append(f"[{i}] {phrase}")

        embed.description = '\n'.join(phrases)

        await ctx.send(embed=embed)
        pass

    @responses.command(name="add")
    @commands.mod_or_permissions(manage_channels=True)
    async def responses_add(self, ctx: commands.Context, *, phrase: str):
        """Adds a phrase for bully responses.

        Args:
            phrase (str): The phrase to add for responses.
        """
        responses = await self.config.guild(ctx.guild).responses()

        if phrase.lower() in responses:
            await ctx.send(f"``{phrase}`` is already a response.")
            return
        
        phrase = re.sub(TRIGGER_REGEX, "", phrase.lower())

        responses.append(phrase)

        await self.config.guild(ctx.guild).responses.set(responses)

        await ctx.send(f"Added ``{phrase}`` to the list of responses.")
        pass

    @responses.command(name="remove")
    @commands.mod_or_permissions(manage_channels=True)
    async def responses_remove(self, ctx: commands.Context, *, phrase: str):
        """Removes a phrase from bully responses.

        Args:
            phrase (str | int): The response.
        """
        responses = await self.config.guild(ctx.guild).responses()

        try:
            phrase = int(phrase)

            if phrase >= len(responses):
                await ctx.send(f"``{phrase}`` is out of range.")
                return
            
            removed_phrase = responses.pop(phrase)
        
        except:
            phrase = re.sub(TRIGGER_REGEX, "", phrase.lower())
            if phrase not in responses:
                await ctx.send(f"``{phrase}`` is not on the responses list.")
                return

            removed_phrase = responses.remove(phrase)
        
        await self.config.guild(ctx.guild).triggers.set(responses)
        await ctx.send(f"Removed ``{removed_phrase}`` to the list of responses for bullying.")
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
            
        if message.guild is None:
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
                    responses = await config.responses()
                    response = replace_tokens(random.choice(
                        responses), member=message.author, use_mentions=True)

                    timeout = await config.timeout_mins()

                    try:
                        await message.reply(response)
                        if timeout > 0:
                            await message.author.timeout(datetime.timedelta(minutes=timeout), reason=response)
                        else:
                            await message.author.kick(reason=response)
                    except Exception as e:
                        # Couldn't timeout or kick the user, which is fine.
                        pass
                    pass

                    cooldown_minutes = await config.cooldown_minutes()

                    await config.cooldown_timestamp.set((datetime.datetime.now() + datetime.timedelta(minutes=d20.roll(cooldown_minutes).total)).timestamp())
