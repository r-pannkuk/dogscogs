import typing
import discord
from redbot.core import commands
from redbot.core.config import Config

from .config import BetConfig

MAX_BAR_WIDTH = 25

class BetEmbed(discord.Embed):
    def __init__(
            self, 
            *args,
            config: Config,
            ctx: commands.GuildContext, 
            bet_config_id: int,
            **kwargs
        ):
        self.config = config
        self.ctx = ctx
        self.bet_config_id = bet_config_id
        self.guild = ctx.guild
        super().__init__(*args, **kwargs)

    async def generate(self) -> "BetEmbed":
        active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
        bet_config : BetConfig = active_bets[str(self.bet_config_id)]

        title_prefix = ""

        if bet_config['state'] == 'open':
            title_prefix = "🎰 "
        elif bet_config['state'] == 'closed':
            title_prefix = "🔒 "
        elif bet_config['state'] == 'cancelled':
            title_prefix = "❌ "
        elif bet_config['state'] == 'resolved':
            title_prefix = "💰 "

        self.title = f"{title_prefix}{bet_config['title']}"
        self.description = bet_config['description']

        class ValueEntry(typing.TypedDict):
            total_value: int
            who: typing.List[int]

        values : typing.Dict[int, ValueEntry]= { 
            option['id']: { 
                'total_value': 0, 
                'who': []
            } 
            for option in bet_config['options'] 
        }
        for better in bet_config['betters']:
            values[better['bet_option_id']]['total_value'] += better['bet_amount']
            values[better['bet_option_id']]['who'].append(better['member_id'])

        bet_total = sum(values[option['id']]['total_value'] for option in bet_config['options'])
        pool_total = bet_total + bet_config['base_value']

        member = self.guild.get_member(bet_config['author_id']) or await self.ctx.bot.fetch_user(bet_config['author_id'])
        parameters_field = ""
        parameters_field += f"__Started By__: {member.mention}\n"
        parameters_field += f"__State__: `{bet_config['state'].capitalize()}`\n"
        if pool_total > 0:
            parameters_field += f"__Total Pool__: **{pool_total}**"
            if bet_total != pool_total: 
                parameters_field += f" : [{bet_total}] ( +{bet_config['base_value']} )"
            parameters_field += "\n"
        if bet_config['minimum_bet'] > 1:
            parameters_field += f"__Minimum Bet__: {bet_config['minimum_bet']}\n"

        self.add_field(name=" ", value=parameters_field, inline=False)

        options_field = ""

        for i, option in enumerate(bet_config['options']):
            options_field += f"{i+1}. "
            if bet_config['state'] == 'resolved' and bet_config['winning_option_id'] == option['id']:
                options_field += f"🎉 __{option['option_name']}__ 🎉: "
            else:
                options_field += f"__{option['option_name']}__: " 
            options_field += f"{values[option['id']]['total_value']}"
            if bet_total > 0:
                count = sum(1 for better in bet_config['betters'] if better['bet_option_id'] == option['id'])
                if count > 0:
                    options_field += f" [{count} User{'s' if count > 1 else ''}]"
                options_field += "\n"

                scale_factor = max(1,(values[option['id']]['total_value'] / bet_total if bet_total > 0 else 0) * MAX_BAR_WIDTH)
                options_field += ''.join(['█' for _ in range(int(scale_factor))])
                options_field += f" ({values[option['id']]['total_value']/bet_total:.2%})"
                options_field += '\n'

            options_field += '\n'

        self.add_field(name="Options", value=options_field, inline=False)

        self.set_footer(text=f"Bet ID: {bet_config['id']}")
        return self

    

