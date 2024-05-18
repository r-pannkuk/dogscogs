import random
import discord

from trigger.config import ReactConfig, ReactType


class ReactConfigurationEmbed(discord.Embed):
    def __init__(self, client: discord.Client, config: ReactConfig):
        self.client = client

        assert config["embed"] is not None
        color = config["embed"]["color"]

        super().__init__(title=f"React Configuration: {config['name']}")
        self.description = ""
        self.description += (
            "__Name__: " + discord.utils.escape_markdown(config["name"]) + "\n"
        )
        self.description += "__Enabled__: " + str(config["enabled"]) + "\n"
        self.description += "\n"
        self.description += (
            "__Cooldown__: " + str(config["cooldown"]["mins"]) + " mins\n"
        )
        self.description += (
            "__Type__: "
            + (ReactType(config["trigger"]["type"] or 0).name or "None")
            + "\n"
        )
        self.description += "__Chance__: " + str(config["trigger"]["chance"]) + "\n"

        if config["trigger"]["type"] & ReactType.MESSAGE:
            if config["trigger"]["list"] and len(config["trigger"]["list"]) > 0:
                self.add_field(
                    name="Triggers",
                    value="\n".join(
                        [
                            discord.utils.escape_markdown(trigger)
                            for trigger in config["trigger"]["list"]
                        ]
                    ),
                    inline=False,
                )

        if config["always_list"] and len(config["always_list"]) > 0:
            user_list = [
                y.mention
                for y in [self.client.get_user(int(x)) for x in config["always_list"]]
                if y is not None
            ]
            self.add_field(
                name="Always Triggers For", value="\n".join(user_list), inline=False
            )

        if config["responses"] and len(config["responses"]) > 0:
            self.add_field(
                name="Responses",
                value="\n".join(
                    [
                        discord.utils.escape_markdown(response)
                        for response in config["responses"]
                    ]
                ),
                inline=False,
            )

        if config["channel_ids"] and len(config["channel_ids"]) > 0:
            channel_list = [
                y.mention
                for y in [
                    self.client.get_channel(int(x)) for x in config["channel_ids"]
                ]
                if y is not None and isinstance(y, discord.TextChannel)
            ]
            self.add_field(
                name="Triggering/Responding In", value="\n".join(channel_list), inline=False
            )
        elif config["trigger"]["type"] & ReactType.MESSAGE:
            self.add_field(name="Triggering In", value="All Channels", inline=False)
        else:
            self.add_field(name="Triggering In", value="None", inline=False)

        response_type = "Using: " + (
            "**Embed**" if config["embed"]["use_embed"] else "**Text**"
        )

        if config["embed"]["use_embed"]:
            response_type += "\n"
            response_type += (
                "__Title__: "
                + discord.utils.escape_markdown((config["embed"]["title"] or ""))
                + "\n"
            )
            response_type += (
                "__Footer__: "
                + discord.utils.escape_markdown((config["embed"]["footer"] or ""))
                + "\n"
            )
            if config["embed"]["color"]:
                response_type += (
                    "__Color__: "
                    + str(discord.Color.from_rgb(*config["embed"]["color"]))
                    + "\n"
                )
            response_type += "__Image__: " + discord.utils.escape_markdown(
                (config["embed"]["image_url"] or "")
            )

        self.add_field(name="Response Type", value=response_type, inline=False)

        self.add_field(name="Stats", value=f"__Last Fire__: <t:{config['cooldown']['last_timestamp']}>\n__Next Avaialble__: <t:{config['cooldown']['next']}>")

class ReactEmbed(discord.Embed):
    def __init__(self, config: ReactConfig):
        if config["embed"] is None or not config["embed"]["use_embed"]:
            raise ValueError("Embed is not enabled for this trigger.")

        super().__init__(
            title=config["embed"]["title"],
            description=config["responses"][0],
            colour=discord.Color.from_rgb(*config["embed"]["color"]),
        )
        if config["embed"]["image_url"]:
            self.set_thumbnail(url=config["embed"]["image_url"])

        if config["embed"]["footer"]:
            self.set_footer(text=config["embed"]["footer"])

            