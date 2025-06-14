import typing
import discord
from redbot.core.config import Config
import datetime

from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect
from dogscogs.constants import TIMEZONE
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS

from clans.config import ClanBattleRecord, ClanConfig, ClanRegistrationConfig, GuildConfig

from ..characters import Characters

LEADERBOARD_ROWS_PER_PAGE = 10

def date_filter_all(br: ClanBattleRecord) -> bool:
    return True

def date_filter_this_month(record: typing.Union[str, ClanBattleRecord, datetime.datetime]) -> bool:
    if isinstance(record, str):
        date = datetime.datetime.fromtimestamp(int(record), tz=TIMEZONE)
    elif isinstance(record, dict):
        if 'created_at' not in record:
            raise ValueError("Record must contain 'created_at' field.")
        date = datetime.datetime.fromtimestamp(record['created_at'], tz=TIMEZONE)
    else:
        date = record
    
    return date >= datetime.datetime.now(tz=TIMEZONE).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def character_filter_all(br: ClanBattleRecord) -> bool:
    return True

def character_filter_specific(registrant_id: str, character_id: str) -> typing.Callable[[ClanBattleRecord], bool]:
    def filter_func(br: ClanBattleRecord) -> bool:
        return (br["player1_character"] == character_id and br["player1_registrant_id"] == registrant_id) or \
               (br["player2_character"] == character_id and br["player2_registrant_id"] == registrant_id)
    return filter_func

class ScoreboardPaginatedEmbed(PaginatedEmbed):
    config : Config
    guild: discord.Guild

    ranking_choice : str = "total_points"
    type_choice : str = "clans"
    period_choice : str = "this_month"
    option_character : str = "REIMU"

    def __init__(
        self,
        *args,
        config : Config,
        interaction : typing.Optional[discord.Interaction] = None,
        original_message: typing.Optional[discord.Message] = None,
        **kwargs,
    ):
        if interaction is None and original_message is None:
            raise ValueError("Either interaction or original_message must be provided.")
        
        async def get_page(index : int) -> typing.Tuple[discord.Embed, int]:

            guild_config : GuildConfig = await config.guild(self.guild).all()

            accumulator : typing.Dict[str, int] = {}

            date_filter = date_filter_all if self.period_choice == "all_time" else date_filter_this_month

            if self.ranking_choice == "total_points":
                for award in guild_config['clan_point_awards'].values():
                    if date_filter(award["created_at"]):
                        if accumulator.get(award["clan_registrant_id"]) is None:
                            accumulator[award["clan_registrant_id"]] = 0
                        accumulator[award["clan_registrant_id"]] += award["points"]
            elif self.ranking_choice == "wins":
                for record in guild_config['clan_battle_records'].values():
                    if date_filter(record):
                        if record["winner_id"] not in accumulator:
                            accumulator[record["winner_id"]] = 0
                        accumulator[record["winner_id"]] += 1

            ranked_list : typing.Union[
                typing.List[typing.Tuple[ClanConfig, int]], 
                typing.List[typing.Tuple[ClanRegistrationConfig, int]]
            ]= []

            if self.type_choice == "clans":
                clan_accumulator : typing.Dict[str, int] = {}

                for registrant_id, points in accumulator.items():
                    clan_id = guild_config["clan_registrants"].get(registrant_id, {}).get("clan_id")
                    if clan_id is not None:
                        clan_accumulator[clan_id] = clan_accumulator.get(clan_id, 0) + points

                for clan_id, points in clan_accumulator.items():
                    clan_config = guild_config["clans"].get(clan_id)
                    if clan_config is not None:
                        ranked_list.append((clan_config['name'], points))

            elif self.type_choice == "members":
                member_accumulator: typing.Dict[str, int] = {}

                for registrant_id, points in accumulator.items():
                    registrant_config = guild_config["clan_registrants"].get(registrant_id)
                    if registrant_config is not None:
                        member_accumulator[registrant_config['member_id']] = member_accumulator.get(registrant_config["member_id"], 0) + points

                for member_id, points in member_accumulator.items():
                    member = self.guild.get_member(int(member_id))
                    if member is not None:
                        ranked_list.append((member.mention, points))
                    else:
                        ranked_list.append((member_id, points))
                        

            elif self.type_choice == "character":
                # Placeholder for character scoreboard logic
                # This should fetch and return the character scoreboard data
                # For now, we return a placeholder embed
                if False:
                    return discord.Embed(
                        title="No Characters", 
                        description=f"There isn't any record in {self.guild.name}.",
                        color=discord.Color.red()
                    ), 1
                
            if len(ranked_list) == 0:
                return discord.Embed(
                    title="No Records", 
                    description=f"No records were found in {self.guild.name}.\n__Type__: {self.type_choice}\n__Ranking__: {self.ranking_choice}\n__Period__: {self.period_choice}.",
                    color=discord.Color.red()
                ), 1
            
            ranked_list.sort(key=lambda x: x[1], reverse=True)
            
            start_index = index * LEADERBOARD_ROWS_PER_PAGE
            end_index = start_index + LEADERBOARD_ROWS_PER_PAGE

            page_items = ranked_list[start_index:end_index]
            embed = discord.Embed(
                title="Clan Battle Scoreboard",
                description=f"__Type__: {self.type_choice}\n__Ranking__: {self.ranking_choice}\n__Period__: {self.period_choice}",
                color=discord.Color.blue()
            )

            text = '\n'.join([
                f"{i + 1 + start_index}. {text} - {points}"
                for i, (text, points) in enumerate(page_items)
            ])

            embed.add_field(
                name="Rankings",
                value=text
            )

            embed.set_footer(text=f"Page {index + 1} of {len(ranked_list) // LEADERBOARD_ROWS_PER_PAGE + 1}")

            return embed, (len(ranked_list) // LEADERBOARD_ROWS_PER_PAGE) + 1

        super().__init__(
            *args, 
            interaction=interaction, 
            message=original_message, 
            get_page=get_page, 
            **kwargs
        )

        self.config = config
        self.guild = self.interaction.guild if self.interaction else self.original_message.guild # type: ignore[assignment,union-attr]
    
    async def send(self) -> "ScoreboardPaginatedEmbed":
        await super().send()

        self.update_buttons()
        await self.edit_page()
        await self.message.edit(view=self)

        return self
    
    def update_buttons(self):
        super().update_buttons()

        self.select_ranking.options = [
            discord.SelectOption(
                label="Total Points",
                value="total_points",
                default=True if self.ranking_choice == "total_points" else False,
            ),
            discord.SelectOption(
                label="Wins",
                value="wins",
                default=True if self.ranking_choice == "wins" else False,
            ),
        ]

        self.select_type.options = [
            discord.SelectOption(
                label="Clans",
                value="clans",
                default=True if self.type_choice == "clans" else False,
            ),
            discord.SelectOption(
                label="Members",
                value="members",
                default=True if self.type_choice == "members" else False,
            ),
            # discord.SelectOption(
            #     label="Character",
            #     value="character",
            #     default=True if self.option_type == "character" else False,
            # )
        ]

        self.select_period.options = [
            discord.SelectOption(
                label="All Time",
                value="all_time",
                default=True if self.period_choice == "all_time" else False,
            ),
            discord.SelectOption(
                label=f"This Month ({datetime.datetime.now(tz=TIMEZONE).strftime('%B')})",
                value="this_month",
                default=True if self.period_choice == "this_month" else False,
            ),
        ]

        # self.select_character.options = [
        #     discord.SelectOption(
        #         label=c["full_name"],
        #         value=ID,
        #         default=True if ID == self.option_character else False,
        #     )
        #     for ID, c in Characters.items()
        # ]
    
    async def edit_page(self):
        
        await super().edit_page()

        return
    

    @discord.ui.select(
        cls=discord.ui.Select,
        custom_id="type_select",
        min_values=1,
        max_values=1,
        options=[]
    )
    async def select_type(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.type_choice = select.values[0]
        await self.edit_page()


    @discord.ui.select(
        cls=discord.ui.Select,
        custom_id="ranking_select",
        min_values=1,
        max_values=1,
        options=[]
    )
    async def select_ranking(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.ranking_choice = select.values[0]
        await self.edit_page()


    # @discord.ui.select(
    #     cls=discord.ui.Select,
    #     custom_id="character_select",
    #     min_values=1,
    #     max_values=1,
    #     options=[
    #     ]
    # )
    # async def select_character(self, interaction: discord.Interaction, select: discord.ui.Select):
        # await interaction.response.defer()
        # self.option_character = select.values[0]
        # await self.edit_page()


    @discord.ui.select(
        cls=discord.ui.Select,
        custom_id="period_select",
        min_values=1,
        max_values=1,
        options=[]
    )
    async def select_period(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        self.period_choice = select.values[0]
        await self.edit_page()