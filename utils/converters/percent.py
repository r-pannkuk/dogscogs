import discord
from redbot.core import commands

class Percent(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            if argument[-1] == '%':
                return float(argument[:-1]) / 100
            return float(argument)
        except:
            return None