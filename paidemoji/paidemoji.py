import datetime
from io import BytesIO
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
import requests  # type: ignore[import-untyped]

from coins.coins import Coins
from paidemoji.classes import EmojiConfigurationPrompt, PaidEmojiConfig, StickerConfigurationPrompt, PaidStickerConfig
from paidemoji.embeds import PaidEmojiEmbed, PaidStickerEmbed
from paidemoji.views import EmojiConfigurationModal, StickerConfigurationModal

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.views.paginated import PaginatedEmbed
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.parsers.emoji import parse_emoji_ids

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]
PurchaseType = Literal["EMOJI", "STICKER"]

DEFAULT_GUILD = {
    "emojis": [],
    "stickers": [],
    "max_emojis": 5,
    "max_stickers": 5,
    "emoji_cost": 100,
    "sticker_cost": 100,
}

class PaidEmoji(commands.Cog):
    """
    Users can pay currency to add an emoji.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    async def __add_emoji(
        self,
        *,
        guild: discord.Guild,
        author: discord.Member,
        name: str,
        image_url: str,
        price: typing.Optional[int],
    ) -> typing.Tuple[discord.Emoji, PaidEmojiConfig]:
        emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            guild
        ).emojis()
        paid_emojis: typing.List[discord.Emoji] = [
            e
            for e in [guild.get_emoji(emoji["id"]) for emoji in emoji_configs]
            if e is not None
        ]
        emoji_configs = [
            emoji
            for emoji in emoji_configs
            if emoji["id"] in [e.id for e in paid_emojis]
        ]

        if image_url in [emoji.url for emoji in paid_emojis]:
            raise ValueError("PaidEmojiConfig already exists.")

        if name in [emoji.name for emoji in paid_emojis]:
            raise ValueError(f"Emoji with the name `{name}` already exists.")

        fetch_image = requests.get(image_url)

        if fetch_image.status_code != 200:
            raise ValueError("Failed to fetch image.")

        if price is None:
            price = await self.config.guild(guild).emoji_cost()

        try:
            emoji = await guild.create_custom_emoji(
                name=name,
                image=fetch_image.content,
                reason=f"Paid Emoji by {author.name} for {price} {await Coins._get_currency_name(guild)}",
            )
        except discord.Forbidden:
            raise ValueError("Bot does not have permission to create emojis.")
        except discord.HTTPException:
            raise ValueError(f"Failed to create emoji. Make sure the image is the right format and not larger than 256 kb.")

        emoji_config = PaidEmojiConfig(
            id=emoji.id,
            type="animated" if emoji.animated else "image",
            author_id=author.id,
            source_url=image_url,
            price=price,
            last_used_at=datetime.datetime.now().timestamp(),
            used_count=0,
        )

        emoji_configs.append(dict(emoji_config))  # type: ignore[arg-type]

        await self.config.guild(guild).emojis.set(emoji_configs)

        return emoji, emoji_config

    async def __remove_emoji(self, guild: discord.Guild, emoji_config: PaidEmojiConfig):
        emoji_configs = await self.config.guild(guild).emojis()
        found_emoji_configs = [
            config for config in emoji_configs if config["id"] == emoji_config["id"]
        ]

        if len(found_emoji_configs) == 0:
            raise ValueError("PaidEmojiConfig not found.")

        found_emoji: typing.Union[discord.Emoji, None] = guild.get_emoji(
            emoji_config["id"]
        )

        if found_emoji is None:
            raise ValueError("Emoji not found.")

        try:
            await found_emoji.delete(reason=f"Paid Emoji removed by command.")
        except discord.Forbidden:
            raise ValueError("Bot does not have permission to delete emojis.")
        except discord.HTTPException:
            raise ValueError("Failed to delete emoji.")

        emoji_configs = [
            config for config in emoji_configs if config["id"] != emoji_config["id"]
        ]
        await self.config.guild(guild).emojis.set(emoji_configs)
        pass

    async def __add_sticker(self,
        *,
        guild: discord.Guild,
        author: discord.Member,
        name: str,
        description: str,
        emoji: str,
        image_url: str,
        price: typing.Optional[int],
    ) -> typing.Tuple[discord.Emoji, PaidEmojiConfig]:
        sticker_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            guild
        ).stickers()
        paid_stickers: typing.List[discord.GuildSticker] = [
            s
            for s in [discord.utils.get(guild.stickers, id=int(sticker['id'])) for sticker in sticker_configs]
            if s is not None
        ]
        sticker_configs = [
            sticker
            for sticker in sticker_configs
            if sticker["id"] in [s.id for s in paid_stickers]
        ]

        if image_url in [sticker.url for sticker in paid_stickers]:
            raise ValueError("PaidStickerConfig already exists.")

        if name in [sticker.name for sticker in paid_stickers]:
            raise ValueError(f"Sticker with the name `{name}` already exists.")

        fetch_image = requests.get(image_url)

        if fetch_image.status_code != 200:
            raise ValueError("Failed to fetch image.")

        if price is None:
            price = await self.config.guild(guild).sticker_cost()

        try:
            sticker = await guild.create_sticker(
                name=name,
                description=description,
                emoji=emoji,
                file=discord.File(BytesIO(fetch_image.content)),
                reason=f"Paid Sticker by {author.name} for {price} {await Coins._get_currency_name(guild)}",
            )
        except discord.Forbidden:
            raise ValueError("Bot does not have permission to create stickers.")
        except discord.HTTPException:
            raise ValueError("Failed to create sticker. Make sure image is in the right format.")

        sticker_config = PaidStickerConfig(
            id=sticker.id,
            author_id=author.id,
            source_url=image_url,
            price=price,
            last_used_at=datetime.datetime.now().timestamp(),
            used_count=0,
        )

        sticker_configs.append(dict(sticker_config))  # type: ignore[arg-type]

        await self.config.guild(guild).stickers.set(sticker_configs)

        return sticker, sticker_config

    async def __remove_sticker(self, guild: discord.Guild, sticker_config: PaidStickerConfig):
        sticker_configs = await self.config.guild(guild).stickers()
        found_sticker_configs = [
            config for config in sticker_configs if config["id"] == sticker_config["id"]
        ]

        if len(found_sticker_configs) == 0:
            raise ValueError("PaidStickerConfig not found.")

        found_sticker: typing.Union[discord.GuildSticker, None] = discord.utils.get(guild.stickers, id=int(sticker_config['id']))

        if found_sticker is None:
            raise ValueError("Sticker not found.")

        try:
            await found_sticker.delete(reason=f"Paid Sticker removed by command.")
        except discord.Forbidden:
            raise ValueError("Bot does not have permission to delete stickers.")
        except discord.HTTPException:
            raise ValueError("Failed to delete sticker.")

        sticker_configs = [
            config for config in sticker_configs if config["id"] != sticker_config["id"]
        ]
        await self.config.guild(guild).stickers.set(sticker_configs)
        pass

    async def __buy(self, ctx: commands.GuildContext, member: discord.Member, cost: int, type: PurchaseType):
        balance = await Coins._get_balance(member)
        currency_name = await Coins._get_currency_name(ctx.guild)

        if balance < cost:
            await ctx.send(
                f"You don't have enough {currency_name} to purchase {type.lower()} slots. `{balance} / {cost}`",
                delete_after=15,
            )
            return
        
        if type == "EMOJI":
            prompt: EmojiConfigurationPrompt = EmojiConfigurationPrompt()  # type: ignore
        else:
            prompt: StickerConfigurationPrompt = StickerConfigurationPrompt() #type: ignore

        async def prompt_user(interaction: discord.Interaction) -> bool:
            if type == "EMOJI":
                modal = EmojiConfigurationModal(ctx)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal:
                    prompt["name"] = modal.name
                    prompt["url"] = modal.url
                    prompt["type"] = modal.type
                    return True
                return False
            elif type == "STICKER":
                modal = StickerConfigurationModal(ctx)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal:
                    prompt["url"] = modal.url
                    prompt["emoji"] = modal.emoji
                    prompt["description"] = modal.description
                    prompt['name'] = modal.name
                    return True
                return False

        view = ConfirmationView(author=ctx.author, callback=prompt_user)
        message = await ctx.reply(
            content=f"Purchase {type.lower()} for `{cost} {currency_name}`?  Current Balance: `{balance}`",
            view=view,
        )

        await view.wait()

        if not view.value:
            await message.edit(
                content="Purchase cancelled.", view=None, delete_after=10
            )
            return
        
        configs : typing.Union[typing.List[PaidStickerConfig], typing.List[PaidEmojiConfig]]
        
        if type == "EMOJI":
            max = await self.config.guild(ctx.guild).max_emojis()
            configs = await self.config.guild(ctx.guild).emojis()
            configs = [c for c in configs if c["type"] == prompt["type"]]
            emoji_slots_remaining = ctx.guild.emoji_limit - len([e for e in ctx.guild.emojis if e.animated == (prompt["type"] == "animated")])
            max = min(max, emoji_slots_remaining + len(configs))
        elif type == "STICKER":
            max = await self.config.guild(ctx.guild).max_stickers()
            configs = await self.config.guild(ctx.guild).stickers()
            sticker_slots_remaining = ctx.guild.sticker_limit - len(ctx.guild.stickers)
            max = min(max, sticker_slots_remaining + len(configs))

        if max == 0:
            await ctx.send(
                f"Could not add or remove paid {type.lower()}. Server has reached the maximum number of {type.lower()} slots."
            )
            return

        if len(configs) >= max:
            found : typing.Union[typing.List[discord.Emoji], typing.List[discord.GuildSticker]]

            if type == "EMOJI":
                found = [
                    e
                    for e in [
                        ctx.guild.get_emoji(emoji["id"])
                        for emoji in configs
                    ]
                    if e is not None
                ]
            elif type == "STICKER":
                found = [
                    s
                    for s in [
                        discord.utils.get(ctx.guild.stickers, id=int(sticker['id']))
                        for sticker in configs
                    ]
                    if s is not None
                ]

            if len(configs) == 0:
                await ctx.send(
                    f"Something went wrong. Could not find matching {type.lower()} on server."
                )
                return

            oldest = sorted(found, key=lambda x: x.created_at)[0]
            oldest_config = [
                c for c in configs if c["id"] == oldest.id
            ][0]

            if type == "EMOJI":
                combined_type_string = f"{str(prompt['type']).lower()} emoji"
            elif type == "STICKER":
                combined_type_string = "sticker"

            view = ConfirmationView(author=ctx.author)
            await message.edit(
                content=f"Maximum number of paid {combined_type_string} reached. ({len(found)} / {max})\n\n"
                + f"Delete {oldest} to make room?\n",
                view=view,
            )

            await view.wait()

            if not view.value:
                await message.edit(
                    content="Purchase cancelled.", view=None, delete_after=10
                )
                return

            try:
                if type == "EMOJI":
                    await self.__remove_emoji(ctx.guild, oldest_config)
                elif type == "STICKER":
                    await self.__remove_sticker(ctx.guild, oldest_config)
            except ValueError as e:
                await ctx.reply(str(e))
                return

        await message.delete()

        try:
            if type == "EMOJI":
                result, _ = await self.__add_emoji(
                    guild=ctx.guild,
                    author=ctx.author,
                    name=prompt["name"],
                    image_url=prompt["url"],
                    price=cost,
                )
            elif type == "STICKER":
                result, _ = await self.__add_sticker(
                    guild=ctx.guild,
                    author=ctx.author,
                    name=prompt["name"],
                    image_url=prompt["url"],
                    description=prompt["description"],
                    emoji=prompt["emoji"],
                    price=cost,
                )

            await Coins._remove_balance(ctx.author, cost)

            await ctx.send(
                f"{type.capitalize()} {result} added by {ctx.author.mention} for {cost} {currency_name}."
            )

        except ValueError as e:
            await ctx.reply(str(e))

    async def __list(self, ctx: commands.GuildContext, type: PurchaseType):
        if type == "EMOJI":
            configs = await self.config.guild(ctx.guild).emojis()
            found = [
                e
                for e in [ctx.guild.get_emoji(emoji["id"]) for emoji in configs]
                if e is not None
            ]
        elif type == "STICKER":
            configs = await self.config.guild(ctx.guild).stickers()
            found = [
                s
                for s in [discord.utils.get(ctx.guild.stickers, id=int(sticker['id'])) for sticker in configs]
                if s is not None
            ]

        updated_configs = [
            c
            for c in configs
            if c["id"] in [f.id for f in found]
        ]

        if len(found) != len(configs):
            if type == "EMOJI":
                await self.config.guild(ctx.guild).emojis.set(updated_configs)
            elif type == "STICKER":
                await self.config.guild(ctx.guild).stickers.set(updated_configs)

        async def get_page(index: int) -> typing.Tuple[discord.Embed, int]:
            if type == "EMOJI":
                configs: typing.List[PaidEmojiConfig] = await self.config.guild(
                    ctx.guild
                ).emojis()
                found = [
                    e
                    for e in [ctx.guild.get_emoji(emoji["id"]) for emoji in configs]
                    if e is not None
                ]
                max_slots = await self.config.guild(ctx.guild).max_emojis()
            elif type == "STICKER":
                configs: typing.List[PaidStickerConfig] = await self.config.guild(
                    ctx.guild
                ).stickers()
                found = [
                    s
                    for s in [discord.utils.get(ctx.guild.stickers, id=int(sticker['id'])) for sticker in configs]
                    if s is not None
                ]
                max_slots = await self.config.guild(ctx.guild).max_stickers()

            if len(configs) == 0:
                return (
                    discord.Embed(
                        title=f"No Paid {type.capitalize()}s found.", color=discord.Color.red()
                    ),
                    1,
                )

            configs.sort(
                key=lambda x: (
                    x["type"] if type == "EMOJI" else "STICKER",
                    [f.created_at for f in found if f.id == x["id"]][0],
                ),
                reverse=True,
            )

            found_config = configs[index]

            if type == "EMOJI":
                matched_type_configs = [
                    c for c in configs if c["type"] == found_config["type"]
                ]
                relative_index = matched_type_configs.index(found_config) + 1
                embed = PaidEmojiEmbed(
                    ctx=ctx,
                    emoji_config=found_config,
                )
                embed.set_footer(
                    text=f"{found_config['type'].capitalize()} Emoji Slot: {relative_index} / {max_slots}"
                )
            elif type == "STICKER":
                relative_index = configs.index(found_config) + 1
                embed = PaidStickerEmbed(
                    ctx=ctx,
                    sticker_config=found_config,
                )
                embed.set_footer(
                    text=f"Sticker Slot: {relative_index} / {max_slots}"
                )

            return embed, len(configs)

        await PaginatedEmbed(message=ctx.message, get_page=get_page).send()

    async def __remove(self, ctx: commands.GuildContext, source: typing.Union[discord.Emoji, discord.GuildSticker], type: PurchaseType):
        if type == "EMOJI":
            configs = await self.config.guild(ctx.guild).emojis()
        elif type == "STICKER":
            configs = await self.config.guild(ctx.guild).stickers()

        found_configs = [
            config for config in configs if config["id"] == source.id
        ]

        if len(found_configs) == 0:
            await ctx.reply(f"Paid {type.lower()} was not found.")
            return

        config = found_configs[0]

        try:
            if type == "EMOJI":
                await self.__remove_emoji(ctx.guild, config)
                await ctx.reply(f"Emoji {source} removed.")
            elif type == "STICKER":
                await self.__remove_sticker(ctx.guild, config)
                await ctx.reply(f"Sticker {source} removed.")
        except ValueError as e:
            await ctx.reply(str(e))
        pass

    ################# EMOJI #################

    @commands.group()
    async def paidemoji(self, ctx: commands.GuildContext):
        """Manage paid emoji. Users can buy static or animated emoji slots by using currency. The oldest emoji slot will be replaced with any new ones created if the slots are full."""
        pass

    @paidemoji.command(name="buy")
    async def emoji_buy(self, ctx: commands.GuildContext):
        """Buy an emoji."""
        await self.__buy(ctx, ctx.author, await self.config.guild(ctx.guild).emoji_cost(), "EMOJI")

    @paidemoji.command(name="list")
    async def emoji_list(self, ctx: commands.GuildContext):
        """List all paid emojis."""
        await self.__list(ctx, "EMOJI")

    @paidemoji.command(name="remove")
    @commands.has_guild_permissions(manage_roles=True)
    async def emoji_remove(self, ctx: commands.GuildContext, emoji: discord.Emoji):
        """Remove a paid emoji."""
        await self.__remove(ctx, emoji, "EMOJI")

    @paidemoji.command(name="cost")
    @commands.has_guild_permissions(manage_roles=True)
    async def emoji_cost(self, ctx: commands.GuildContext, cost: typing.Optional[int]):
        """Set the cost of adding an emoji."""
        if cost is None:
            cost = await self.config.guild(ctx.guild).emoji_cost()

        await self.config.guild(ctx.guild).emoji_cost.set(cost)
        await ctx.reply(
            f"Base cost of adding an emoji set to `{cost} {await Coins._get_currency_name(ctx.guild)}`."
        )
        pass

    ################# STICKERS #################

    @commands.group()
    async def paidstickers(self, ctx: commands.GuildContext):
        """Manage paid stickers. Users can buy sticker slots with currency. The oldest sticker slot will be replaced with any new ones created if the slots are full."""
        pass

    @paidstickers.command(name="buy")
    async def sticker_buy(self, ctx: commands.GuildContext):
        """Buy a sticker."""
        await self.__buy(ctx, ctx.author, await self.config.guild(ctx.guild).sticker_cost(), "STICKER")

    @paidstickers.command(name="list")
    async def sticker_list(self, ctx: commands.GuildContext):
        """List all paid stickers."""
        await self.__list(ctx, "STICKER")

    @paidstickers.command(name="remove")
    @commands.has_guild_permissions(manage_roles=True)
    async def sticker_remove(self, ctx: commands.GuildContext, sticker: discord.GuildSticker):
        """Remove a paid emoji."""
        await self.__remove(ctx, sticker, "STICKER")

    @paidstickers.command(name="cost")
    @commands.has_guild_permissions(manage_roles=True)
    async def sticker_cost(self, ctx: commands.GuildContext, cost: typing.Optional[int]):
        """Set the cost of adding a sticker."""
        if cost is None:
            cost = await self.config.guild(ctx.guild).sticker_cost()

        await self.config.guild(ctx.guild).sticker_cost.set(cost)
        await ctx.reply(
            f"Base cost of adding a sticker set to `{cost} {await Coins._get_currency_name(ctx.guild)}`."
        )
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            message.guild
        ).emojis()
        changed = False

        found_emoji_ids = parse_emoji_ids(message.content)

        for i in range(len(emoji_configs)):
            emoji_config = emoji_configs[i]

            if emoji_config["id"] in found_emoji_ids:
                emoji_configs[i]["used_count"] += 1
                emoji_configs[i]["last_used_at"] = datetime.datetime.now().timestamp()
                changed = True

        if changed:
            await self.config.guild(message.guild).emojis.set(emoji_configs)

        sticker_configs: typing.List[PaidStickerConfig] = await self.config.guild(
            message.guild
        ).stickers()
        changed = False

        found_sticker_ids = [sticker.id for sticker in message.stickers]

        for i in range(len(sticker_configs)):
            sticker_config = sticker_configs[i]

            if sticker_config["id"] in found_sticker_ids:
                sticker_configs[i]["used_count"] += 1
                sticker_configs[i]["last_used_at"] = datetime.datetime.now().timestamp()
                changed = True

        if changed:
            await self.config.guild(message.guild).stickers.set(sticker_configs)

        pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot:
            return

        if not reaction.is_custom_emoji():
            return

        emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            reaction.message.guild
        ).emojis()
        changed = False

        for i in range(len(emoji_configs)):
            emoji_config = emoji_configs[i]

            if reaction.emoji.id == emoji_config["id"]:  # type: ignore[union-attr]
                emoji_configs[i]["used_count"] += 1
                emoji_configs[i]["last_used_at"] = datetime.datetime.now().timestamp()
                changed = True

        if changed:
            await self.config.guild(reaction.message.guild).emojis.set(emoji_configs)
        pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(
        self,
        guild: discord.Guild,
        before: typing.List[discord.Emoji],
        after: typing.List[discord.Emoji],
    ):
        emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            guild
        ).emojis()
        changed = False

        emoji_configs = [
            ec for ec in emoji_configs if ec["id"] in [e.id for e in after]
        ]
        found_after = {
            ec["id"]: [e for e in after if e.id == ec["id"]][0] for ec in emoji_configs
        }

        await self.config.guild(guild).emojis.set(emoji_configs)
        pass

    @commands.Cog.listener()
    async def on_guild_stickers_update(
        self,
        guild: discord.Guild,
        before: typing.List[discord.GuildSticker],
        after: typing.List[discord.GuildSticker],
    ):
        sticker_configs: typing.List[PaidStickerConfig] = await self.config.guild(
            guild
        ).stickers()
        changed = False

        sticker_configs = [
            sc for sc in sticker_configs if sc["id"] in [s.id for s in after]
        ]
        found_after = {
            sc["id"]: [s for s in after if s.id == sc["id"]][0] for sc in sticker_configs
        }

        await self.config.guild(guild).stickers.set(sticker_configs)
        pass