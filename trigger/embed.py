import discord

from trigger.config import ReactConfig, ReactType


class ReactConfigurationEmbed(discord.Embed):
    def __init__(self, client: discord.Client, config: ReactConfig):
        self.client = client

        assert config["embed"] is not None
        color = config["embed"]["color"]

        super().__init__(title=f"React Configuration: {config['name']}")
        self.description = "__Chance__: " + str(config["trigger"]["chance"]) + "\n"
        self.description += "\n"
        self.description += "__Type__: " + (config["trigger"]["type"].name or "None") + "\n"
        self.description += "__Cooldown__: " + str(config["cooldown"]["mins"]) + " mins\n"

        if config["trigger"]["type"] & ReactType.MESSAGE:
            if config["trigger"]["list"] and len(config["trigger"]["list"]) > 0:
                self.add_field(name="Triggers", value="\n".join(config["trigger"]["list"]), inline=False)

        if config["channel_ids"] and len(config["channel_ids"]) > 0:
            channel_list = [y.mention for y in [self.client.get_channel(int(x)) for x in config["channel_ids"]] if y is not None]
            self.add_field(name="Triggering In", value="\n".join(channel_list), inline=False)
        else:
            self.add_field(name="Triggering In", value="All Channels", inline=False)

        response_type = "Using: " + ("**Embed**" if config["embed"]["use_embed"] else "**Text**")
        
        if config["embed"]["use_embed"]:
            response_type += "\n"
            response_type += "__Title__: " + (config["embed"]["title"] or "") + "\n"
            if config["embed"]["color"]:
                response_type += "__Color__: " + str(discord.Color.from_rgb(*config["embed"]["color"])) + "\n"
            response_type += "__Footer__: " + (config["embed"]["footer"] or "") + "\n"
            response_type += "__Image__: " + (config["embed"]["image_url"] or "")

        self.add_field(name="Response Type", value=response_type, inline=False)

        if config["responses"] and len(config["responses"]) > 0:
            self.add_field(name="Responses", value="\n".join(config["responses"]), inline=False)

        if config["always_list"] and len(config["always_list"]) > 0:
            user_list = [y.mention for y in [self.client.get_user(int(x)) for x in config["always_list"]] if y is not None]
            self.add_field(name="Always Triggers For", value="\n".join(user_list), inline=False)
        

