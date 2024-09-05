from redbot.core import commands

class PercentageOrFloat(commands.Converter):
    @staticmethod
    def to_float_or_percentage(argument: str) -> float:
        is_percentage = False
        if argument.endswith("%"):
            argument = argument[:-1]
            is_percentage = True

        value = float(argument)
        if is_percentage:
            value /= 100

        return value

    async def convert(self, ctx, argument: str) -> float:
        try:
            value = PercentageOrFloat.to_float_or_percentage(argument)
        except ValueError:
            raise commands.BadArgument("Invalid percentage. Must be a float.")

        if value < 0 or value > 1:
            raise commands.BadArgument("Invalid percentage. Must be between 0 and 1.")

        return value
