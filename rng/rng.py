import asyncio
from typing import Literal
import typing

import discord
import random
import d20
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "ask": {
        "delay_ms": 5000,
        "affirmative": {
            "weight": 0.45,
            "responses": [
                "It is certain.",
                "It is decidedly so.",
                "Without a doubt.",
                "Yes definitely.",
                "You may rely on it.",
                "As I see it, yes.",
                "Most likely.",
                "Outlook good.",
                "Yes.",
                "Signs point to yes."
            ]
        },
        "neutral": {
            "weight": 0.1,
            "responses": [
                "Reply hazy, try again.",
                "Ask again later.",
                "Better not tell you now.",
                "Cannot predict now.",
                "Concentrate and ask again."
            ]
        },
        "negative": {
            "weight": 0.45,
            "responses": [
                "Don't count on it.",
                "My reply is no.",
                "My sources say no.",
                "Outlook not so good.",
                "Very doubtful."
            ]
        }
    }
}


class Random(commands.Cog):
    """
    Random functions for ease of use.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        """This sets up the default structure for a new guild."""
        self.config.register_guild(**DEFAULT_GUILD)

        pass

    def choose_distinct_many(self, number: int, options: typing.List[str]) -> typing.List[str]:
        """Chooses many items from a list, up to number.

        __Args__:
            number (int): The number of items to select.

        Returns:
            typing.List[str]: A list of choices selected.
        """
        chosen = []
        values = list.copy(options)
        for i in range(number):
            selected = random.choice(values)
            chosen.append(selected)
            values.remove(selected)
        return chosen

    def chooser(self, ctx: commands.Context, number: int, options: typing.List[str]) -> discord.Embed:
        """Chooses from a list and returns a discord Embed object.

        __Args__:
            ctx (commands.Context): Command Context for the invocation.
            number (int, optional): The number of choices. Defaults to 1.

        Returns:
            discord.Embed: The embed object returned to the user with choices.
        """
        if len(options) == 0:
            raise ValueError("Please enter some options to choose from.")
        if number > len(options):
            raise ValueError("Cannot choose more than list provided.")

        options = [option.rstrip(', ').lstrip(', ') for option in options]

        choices = self.choose_distinct_many(number, options)

        options = sorted(options, key=lambda x: str.lower(x))

        for i in range(len(options)):
            if options[i] in choices:
                options[i] = f"**{options[i]}**"

        embed = discord.Embed(
            title=f"Choice of {number}:",
            description='\n'.join(choices)
        )

        return embed

    async def _choose(self, ctx: commands.Context, number: int, options: typing.Tuple[str]):
        """Helper function to dynamically choose and send an embed based off a list.

        __Args__:
            ctx (commands.Context): Command Context.
            number (int): The number of options to select.
            options (typing.Tuple[str]): The options to select from.
        """
        try:
            await ctx.send(embed=self.chooser(ctx, number, list(options)))
        except ValueError as e:
            await ctx.send(e)

        pass

    @commands.command(usage="<option 1> <option 2>...")
    async def choose(self, ctx: commands.Context, *options):
        """Chooses options from a predetermined list. 

        __Aliases__:
            choose1
            choose2
            ...
            choose9

        __Args__:
            ctx (commands.Context): Command Context.
            *options ([str]): The options available to choose from.
        """
        await self._choose(ctx, 1, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose1(self, ctx: commands.Context, *options):
        await self._choose(ctx, 1, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose2(self, ctx: commands.Context, *options):
        await self._choose(ctx, 2, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose3(self, ctx: commands.Context, *options):
        await self._choose(ctx, 3, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose4(self, ctx: commands.Context, *options):
        await self._choose(ctx, 4, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose5(self, ctx: commands.Context, *options):
        await self._choose(ctx, 5, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose6(self, ctx: commands.Context, *options):
        await self._choose(ctx, 6, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose7(self, ctx: commands.Context, *options):
        await self._choose(ctx, 7, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose8(self, ctx: commands.Context, *options):
        await self._choose(ctx, 8, options)
        pass

    @commands.command(hidden=True, usage="<option 1> <option 2>...")
    async def choose9(self, ctx: commands.Context, *options):
        await self._choose(ctx, 9, options)
        pass

    @commands.command()
    async def roll(self, ctx: commands.Context, *, dice_string: str = "1d6"):
        """Rolls dice and performs operations on them.

        __Syntax__: https://d20.readthedocs.io/en/latest/start.html#dice-syntax

        __Args__:
            ctx (commands.Context): Command Context.
            dice_string (str, optional): A string containing a dice expression. Defaults to "1d6".
        """
        try:
            parsed = d20.roll(dice_string, allow_comments=True)
            description = ""

            for i in range(len(parsed.expr.set)):
                if parsed.expr.set[i].annotation != None:
                    parsed.expr.set[i].annotation += "\n"
                pass
            await ctx.reply(embed=discord.Embed(
                title=f":game_die: Result: {parsed.total}",
                description=parsed.result
            ))
        except d20.errors.TooManyRolls as e:
            await ctx.reply("ERROR: Unable to perform that many rolls.")
        except (d20.errors.RollSyntaxError, d20.errors.RollValueError) as e:
            errormsg = f"Unable to process ``{e.got}``.  Please use one of:\n* "

            expected = list.copy(list(e.expected))
            expected = list(filter(lambda x: x != "D", expected))

            for i in range(len(expected)):
                if expected[i] == 'DECIMAL' or expected[i] == "INTEGER":
                    expected[i] = "NUMBER"
                elif expected[i] == "U_OP":
                    expected[i] = "OPERATOR"

            expected = list(set(expected))

            errormsg += '\n* '.join(expected)
            await ctx.reply(errormsg)
        pass

    @commands.command(aliases=["8ball"])
    async def ask(self, ctx: commands.Context, *, question: str):
        """Asks the magic 8 ball a question, and generates a response.

        __Args__:
            ctx (commands.Context): Command Context.
            question (str): The question to ask the 8 ball.
        """
        ask = await self.config.guild(ctx.guild).ask()
        affirmative = ask['affirmative']
        neutral = ask['neutral']
        negative = ask['negative']
        responses = [response for sublist in random.choices(
            population=[
                affirmative['responses'],
                neutral['responses'],
                negative['responses']
            ],
            weights=[
                affirmative['weight'],
                neutral['weight'],
                negative['weight']
            ]
        ) for response in sublist]

        choice = random.choice(responses)
        embed = discord.Embed(
            title="",
            description=""
        )
        embed.add_field(
            name=f":question: {ctx.author.display_name} asked...",
            value=question,
            inline=True
        )
        answer_field_name = f"\n:8ball: responds..."
        embed.add_field(
            name=answer_field_name,
            value=".",
            inline=False
        )
        interval = ask['delay_ms'] / 1000 / 3
        message : discord.Message = await ctx.send(embed=embed)
        await asyncio.sleep(interval)
        embed.set_field_at(1, name=answer_field_name, value=". .", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(interval)
        embed.set_field_at(1, name=answer_field_name, value=". . .", inline=False)
        await message.edit(embed=embed)
        await asyncio.sleep(interval)
        embed.set_field_at(1, name=answer_field_name, value=choice, inline=False)
        if responses == affirmative["responses"]:
            embed.color = discord.Color.green()
        elif responses == neutral["responses"]:
            embed.color = discord.Color.gold()
        elif responses == negative["responses"]:
            embed.color = discord.Color.red()
        await message.edit(embed=embed)
        


        pass

    # @commands.group()
    # @commands.mod_or_permissions(manage_channels=True)
    # async def rng(self, ctx: commands.Context):
    #     pass

    # @random.group()
    # @commands.mod_or_permissions(manage_channels=True)
    # async def ask(self, ctx: commands.Context):
    #     pass

    # @ask.command()
    # @commands.mod_or_permissions(manage_channels=True)
    # async def answers(self, ctx: commands.Context):
    #     pass

    # @ask.command()
    # @commands.mod_or_permissions(manage_channels=True)
    # async def remove_answer(self, ctx: commands.Context, index: int):
    #     pass

    # @ask.command()
    # @commands.mod_or_permissions(manage_channels=True)
    # async def add_answer(self, ctx: commands.Context, text: str):
    #     pass
