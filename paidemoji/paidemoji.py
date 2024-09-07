import datetime
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
import requests  # type: ignore[import-untyped]

from coins.coins import Coins
from paidemoji.classes import EmojiConfigurationPrompt, PaidEmojiConfig
from paidemoji.embeds import PaidEmojiEmbed
from paidemoji.views import EmojiConfigurationModal
from .paginated import PaginatedEmbed
from .parsers import parse_emoji_ids
from .views import ConfirmationView

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


DEFAULT_GUILD = {
    "emojis": [],
    "max_emojis": 5,
    "cost": 100,
}


class PaidEmoji(commands.Cog):
    """
    Users can pay currency to add an emoji.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    async def _add_emoji(
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
            price = await self.config.guild(guild).cost()

        try:
            emoji = await guild.create_custom_emoji(
                name=name,
                image=fetch_image.content,
                reason=f"Paid Emoji by {author.name} for {price} {await Coins._get_currency_name(guild)}",
            )
        except discord.Forbidden:
            raise ValueError("Bot does not have permission to create emojis.")
        except discord.HTTPException:
            raise ValueError("Failed to create emoji.")

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

    async def _remove_emoji(self, guild: discord.Guild, emoji_config: PaidEmojiConfig):
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

    @commands.group()
    async def paidemoji(self, ctx: commands.GuildContext):
        """Manage paid emoji. Users can buy static or animated emoji slots by using currency. The oldest emoji slot will be replaced with any new ones created if the slots are full."""
        pass

    @paidemoji.command()
    async def buy(self, ctx: commands.GuildContext):
        """Buy an emoji."""
        author_balance = await Coins._get_balance(ctx.author)
        currency_name = await Coins._get_currency_name(ctx.guild)
        cost = await self.config.guild(ctx.guild).cost()

        if author_balance < cost:
            await ctx.send(
                f"You don't have enough {currency_name} to buy an emoji. `{author_balance} / {cost}`",
                delete_after=15,
            )
            return

        prompt: EmojiConfigurationPrompt = EmojiConfigurationPrompt()  # type: ignore

        async def prompt_user(interaction: discord.Interaction) -> bool:
            modal = EmojiConfigurationModal(ctx)
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal:
                prompt["name"] = modal.name
                prompt["url"] = modal.url
                prompt["type"] = modal.type
                return True
            return False

        view = ConfirmationView(author=ctx.author, callback=prompt_user)
        message = await ctx.reply(
            content=f"Purchase an emoji for `{cost} {currency_name}`?  Current Balance: `{author_balance}`",
            view=view,
        )

        await view.wait()

        if not view.value:
            await message.edit(
                content="Purchase cancelled.", view=None, delete_after=10
            )
            return

        max_emoji = await self.config.guild(ctx.guild).max_emojis()
        emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
            ctx.guild
        ).emojis()
        matched_type_emoji_configs = [
            c for c in emoji_configs if c["type"] == prompt["type"]
        ]

        if len(matched_type_emoji_configs) >= max_emoji:
            found_matched_emojis = [
                e
                for e in [
                    ctx.guild.get_emoji(emoji["id"])
                    for emoji in matched_type_emoji_configs
                ]
                if e is not None
            ]
            if len(found_matched_emojis) == 0:
                await ctx.send(
                    "Something went wrong. Could not find matching emojis on server."
                )
                return

            oldest_emoji = sorted(found_matched_emojis, key=lambda x: x.created_at)[0]
            oldest_emoji_config = [
                c for c in emoji_configs if c["id"] == oldest_emoji.id
            ][0]

            view = ConfirmationView(author=ctx.author)
            await message.edit(
                content=f"Maximum number of paid {str(prompt['type']).lower()} emojis reached. ({len(found_matched_emojis)} / {max_emoji})\n\n"
                + f"Delete {oldest_emoji} to make room?\n",
                view=view,
            )

            await view.wait()

            if not view.value:
                await message.edit(
                    content="Purchase cancelled.", view=None, delete_after=10
                )
                return

            try:
                await self._remove_emoji(ctx.guild, oldest_emoji_config)
            except ValueError as e:
                await ctx.reply(str(e))
                return

        await message.delete()

        try:
            emoji, _ = await self._add_emoji(
                guild=ctx.guild,
                author=ctx.author,
                name=prompt["name"],
                image_url=prompt["url"],
                price=cost,
            )

            await Coins._remove_balance(ctx.author, cost)

            await ctx.send(
                f"Emoji {emoji} added by {ctx.author.mention} for {cost} {currency_name}."
            )

        except ValueError as e:
            await ctx.reply(str(e))

    @paidemoji.command()
    async def list(self, ctx: commands.GuildContext):
        """List all paid emojis."""
        emoji_configs = await self.config.guild(ctx.guild).emojis()
        found_emojis = [
            e
            for e in [ctx.guild.get_emoji(emoji["id"]) for emoji in emoji_configs]
            if e is not None
        ]
        updated_emoji_configs = [
            emoji
            for emoji in emoji_configs
            if emoji["id"] in [e.id for e in found_emojis]
        ]

        if len(found_emojis) != len(emoji_configs):
            await self.config.guild(ctx.guild).emojis.set(updated_emoji_configs)

        async def get_page(index: int) -> typing.Tuple[discord.Embed, int]:
            emoji_configs: typing.List[PaidEmojiConfig] = await self.config.guild(
                ctx.guild
            ).emojis()

            if len(emoji_configs) == 0:
                return (
                    discord.Embed(
                        title="No Paid Emoji found.", color=discord.Color.red()
                    ),
                    1,
                )

            emoji_configs.sort(
                key=lambda x: (
                    x["type"],
                    [e.created_at for e in found_emojis if e.id == x["id"]][0],
                ),
                reverse=True,
            )

            found_config = emoji_configs[index]
            matched_type_configs = [
                c for c in emoji_configs if c["type"] == found_config["type"]
            ]
            max_slots = await self.config.guild(ctx.guild).max_emojis()
            relative_index = matched_type_configs.index(found_config) + 1

            embed = PaidEmojiEmbed(
                ctx=ctx,
                emoji_config=found_config,
            )

            embed.set_footer(
                text=f"{found_config['type'].capitalize()} Slot: {relative_index} / {max_slots}"
            )

            return embed, len(emoji_configs)

        await PaginatedEmbed(message=ctx.message, get_page=get_page).send()

    @paidemoji.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def remove(self, ctx: commands.GuildContext, emoji: discord.Emoji):
        """Remove a paid emoji."""
        emoji_configs = await self.config.guild(ctx.guild).emojis()
        found_emoji_configs = [
            config for config in emoji_configs if config["id"] == emoji.id
        ]

        if len(found_emoji_configs) == 0:
            await ctx.reply("Paid Emoji was not found.")
            return

        emoji_config = found_emoji_configs[0]

        try:
            await self._remove_emoji(ctx.guild, emoji_config)
            await ctx.reply(f"Emoji {emoji} removed.")
        except ValueError as e:
            await ctx.reply(str(e))
        pass

    @paidemoji.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def cost(self, ctx: commands.GuildContext, cost: typing.Optional[int]):
        """Set the cost of adding an emoji."""
        if cost is None:
            cost = await self.config.guild(ctx.guild).cost()

        await self.config.guild(ctx.guild).cost.set(cost)
        await ctx.reply(
            f"Base cost of adding an emoji set to `{cost} {await Coins._get_currency_name(ctx.guild)}`."
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
