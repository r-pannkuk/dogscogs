import typing
import discord
from redbot.core import commands
import d20 # type: ignore[import-untyped]

class PercentageOrFloat(commands.Converter):
    @staticmethod
    def to_float_or_percentage(input: str) -> float:
        if input[-1] == "%":
            f = float(input[:-1]) / 100
        else:
            f = float(input)
        return f

    async def convert(self, ctx, argument: str) -> float:
        try:
            value = PercentageOrFloat.to_float_or_percentage(argument)
        except ValueError:
            raise commands.BadArgument("Invalid percentage. Must be a float.")

        return value

class PercentageOrDiceRoll(commands.Converter):
    @staticmethod
    def to_percent_or_diceroll(input: str) -> typing.Union[float, str]:
        """Converts a string to a float or a d20 roll.

        Args:
            input (str): The string argument input.

        Returns:
            typing.Union[float, str]: A float if it's a percentage, or a string if it's a d20 roll.
        """
        try:
            return PercentageOrFloat.to_float_or_percentage(input)
        except ValueError:
            d20.parse(input)
            return input
        
    async def convert(self, ctx, argument: str) -> typing.Union[float, str]:
        try: 
            return PercentageOrDiceRoll.to_percent_or_diceroll(argument)
        except ValueError:
            raise commands.BadArgument("Invalid percentage or dice roll.")
