import abc
from functools import partial
import re
import typing
import discord
import d20

from redbot.core.commands.context import Context
from redbot.core.config import Config

from trigger.config import ReactConfig, ReactType, COG_IDENTIFIER

from trigger.embed import ReactConfigurationEmbed
from dogscogs_utils.adapters.parsers import Token


async def validate_true(str: str, interaction: discord.Interaction):
    return True


async def validate_not_in_guild(input: str, interaction: discord.Interaction):
    guild_config = Config.get_conf(
        None, identifier=COG_IDENTIFIER, force_registration=True, cog_name="Trigger"
    )
    reacts = await guild_config.guild(interaction.guild).reacts()
    return input.lower() not in reacts


async def validate_number_or_diceroll(input: str, interaction: discord.Interaction):
    try:
        float(input)
        return True
    except ValueError:
        try:
            d20.parse(input)
            return True
        except d20.RollSyntaxError:
            return False


async def validate_percent_or_diceroll(input: str, interaction: discord.Interaction):
    try:
        if input[-1] == "%":
            f = float(input[:-1]) / 100
        else:
            f = float(input)
        return 0 <= f <= 1
    except ValueError:
        try:
            d20.parse(input)
            return True
        except d20.RollSyntaxError:
            return False

async def validate_not_in_triggers(trigger_list: typing.List[str], input: str, interaction: discord.Interaction):
    return input.lower() not in trigger_list

async def validate_image(input: str, interaction: discord.Interaction):
    return re.match("(http)?s?:?(\\/\\/[^\"']*\\.(?:png|jpg|jpeg|gif|png|svg))", input) is not None

async def validate_length(length: int, input: str, interaction: discord.Interaction):
    return len(input) <= length

def convert_color_name(input: str) -> discord.Color:
    return discord.Colour.__dict__[input.lower().replace(' ', '_')].__func__(discord.Colour)

def convert_hex_code(input: str) -> discord.Color:
    return discord.Color.from_str(input)

def convert_color_tuple(input: str) -> discord.Color:
    return discord.Color.from_rgb(*map(int, re.sub(r"[^0-9,]", "", input).split(',')))

def convert_to_color(input: str):
    try:
        return convert_hex_code(input)
    except:
        try:
            return convert_color_tuple(input)
        except:
            return convert_color_name(input)
            

async def validate_color(input: str, interaction: discord.Interaction):
    try:
        convert_to_color(input)
        return True
    except: 
        return False

class _EditReactView(abc.ABC, discord.ui.View):
    # finished: bool = False
    embed_message: discord.Message
    selection: typing.Optional[str]

    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(timeout=86400)
        assert message is not None
        self.embed_message = message
        self.selection = None
        self.config = config

    @abc.abstractmethod
    def generate_prompt(self) -> None:
        self.clear_items()
        pass

class ReactTextBasedModal(discord.ui.Modal):
    def __init__(
        self,
        obj,
        key: typing.Union[str, int],
        *,
        react_view: _EditReactView,
        converter: typing.Callable[[str], typing.Any] = lambda x: str(x),
        style: discord.TextStyle = discord.TextStyle.short,
        placeholder: typing.Optional[str] = None,
        required: bool = False,
        validation: typing.Callable[
            [str, discord.Interaction], typing.Awaitable[bool]
        ] = validate_true,
    ):
        self.label: str = key if isinstance(key, str) else "Element " + str(key)
        super().__init__(timeout=86400, title="Edit " + self.label.capitalize()[0:39])
        self.obj = obj
        self.key = key
        self.react_view = react_view
        self.style = style
        self.converter = converter
        self.validation = validation
        
        if isinstance(obj, list):
            if isinstance(key, int):
                if key < len(obj):
                    default = obj[key]
                else:
                    default = None
            else:
                default = key
        else:
            default = obj[key]

        if placeholder == None:
            placeholder = f"Provide a new value for {self.label.capitalize()}."

        self.item: discord.ui.TextInput = discord.ui.TextInput(
            label=self.label[0:44],
            placeholder=placeholder[0:99],
            default=str(default) if default is not None else None,
            style=self.style,
            required=required,
        )
        self.add_item(self.item)

    async def interaction_check(self, interaction: discord.Interaction):
        if not await self.validation(self.item.value, interaction):
            await interaction.response.send_message(
                f"Invalid input for {self.label.capitalize()}. Please try again.",
                ephemeral=True,
                delete_after=10,
            )
            return False
        return True

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key
        value = self.converter(self.item.value)
        if isinstance(self.obj, list):
            if isinstance(key, int) and key < len(self.obj):
                self.obj[key] = value
            elif key in self.obj:
                key = self.obj.index(key)
                self.obj[key] = value
            else:
                self.obj.append(value)
                key = len(self.obj) - 1
        else:
            self.obj[key] = value
        
        await interaction.response.defer(ephemeral=True)

class ReactDynamicButton(abc.ABC, discord.ui.Button):
    def __init__(
        self,
        *,
        obj,
        key: typing.Union[str, int],
        react_view: _EditReactView,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        disabled : bool = False,
        row: int = 0,
    ):
        self.obj = obj
        self.key = key
        self.react_view = react_view
        self.row = row

        super().__init__(label=label, style=style, row=row, disabled=disabled)

    @abc.abstractmethod
    async def callback(self, interaction: discord.Interaction):
        self.react_view.generate_prompt()
        await self.react_view.embed_message.edit(
            embed=ReactConfigurationEmbed(interaction.client, self.react_view.config),
            content=self.react_view.embed_message.content
        )
        if interaction.message is not None:
            await interaction.message.edit(view=self.react_view)

class ReactTextBasedModalButton(ReactDynamicButton):
    def __init__(
        self,
        *,
        obj,
        key: typing.Union[str, int],
        react_view: _EditReactView,
        label: str,
        button_style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        prompt_style: discord.TextStyle = discord.TextStyle.short,
        placeholder: typing.Optional[str] = None,
        required: bool = False,
        disabled : bool = False,
        converter: typing.Callable[[str], typing.Any] = lambda x: str(x),
        validation: typing.Callable[
            [str, discord.Interaction], typing.Awaitable[bool]
        ] = validate_true,
        row: int = 0,
    ):
        super().__init__(
            obj=obj,
            key=key,
            react_view=react_view,
            label=label,
            style=button_style,
            row=row,
            disabled=disabled,
        )

        self.prompt_style = prompt_style
        self.placeholder = placeholder
        self.required = required
        self.converter = converter
        self.validation = validation

    async def callback(self, interaction: discord.Interaction):
        modal = ReactTextBasedModal(
                self.obj,
                self.key,
                react_view=self.react_view,
                converter=self.converter,
                style=self.prompt_style,
                placeholder=self.placeholder,
                required=self.required,
                validation=self.validation,
            )
        await interaction.response.send_modal(modal)
        await modal.wait()
        await super().callback(interaction)

class ReactRemoveEntryButton(ReactDynamicButton):
    def __init__(
        self,
        *,
        obj,
        key: typing.Union[str, int],
        react_view: _EditReactView,
        label: str,
        style: discord.ButtonStyle = discord.ButtonStyle.secondary,
        disabled : bool = False,
        row: int = 0,
    ):
        super().__init__(
            obj=obj,
            key=key,
            react_view=react_view,
            label=label,
            style=style,
            row=row,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        if isinstance(self.obj, list):
            if isinstance(self.key, int):
                self.obj.remove(self.obj[self.key])
            else:
                self.obj.remove(self.key)
        else:
            del self.obj[self.key]
        await super().callback(interaction)
        await interaction.response.defer(ephemeral=True)

class EditReactGeneralView(_EditReactView):
    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(config, message)
        self.generate_prompt()

    def generate_prompt(self) -> None:
        super().generate_prompt()

        self.add_button = ReactTextBasedModalButton(
            obj=self.config,
            key="name",
            react_view=self,
            label="Edit Name",
            row=0,
            prompt_style=discord.TextStyle.long,
            placeholder="Enter a new name for the trigger.",
            required=True,
            converter=lambda s: s.replace(" ", "_").lower(),
            validation=validate_not_in_guild,
        )
        self.add_item(self.add_button)

        self.add_button = ReactTextBasedModalButton(
            obj=self.config["cooldown"],
            key="mins",
            react_view=self,
            label="Edit Cooldown",
            row=0,
            prompt_style=discord.TextStyle.short,
            placeholder="Enter a number between 0 and 1, or a diceroll like `1d30`.",
            required=True,
            validation=validate_number_or_diceroll,
        )
        self.add_item(self.add_button)

class ReactDynamicSelect(abc.ABC, discord.ui.Select):
    def __init__(
            self, 
            *,
            react_view: _EditReactView, 
            options: typing.List[discord.SelectOption],
            custom_id: str,
            min_values: int = 1,
            max_values: int = 1,
            disabled: bool = False,
            placeholder: typing.Optional[str] = None,
            row: int = 0,
        ):
        self.config = react_view.config
        self.react_view = react_view

        super().__init__(
            custom_id=custom_id,
            options=options,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.react_view.generate_prompt()
        await self.react_view.embed_message.edit(
            embed=ReactConfigurationEmbed(interaction.client, self.react_view.config),
            content=self.react_view.embed_message.content,
        )
        if interaction.message is not None:
            await interaction.message.edit(view=self.react_view)
        await interaction.response.defer(ephemeral=True)

class ReactDynamicSelectUsers(abc.ABC, discord.ui.UserSelect):
    def __init__(
            self, 
            *,
            react_view: _EditReactView, 
            custom_id: str,
            min_values: int = 1,
            max_values: int = 1,
            disabled: bool = False,
            placeholder: typing.Optional[str] = None,
            row: int = 0,
        ):
        self.config = react_view.config
        self.react_view = react_view

        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.react_view.config["always_list"] = [user.id for user in self.values]
        self.react_view.generate_prompt()
        await self.react_view.embed_message.edit(
            embed=ReactConfigurationEmbed(interaction.client, self.react_view.config),
            content=self.react_view.embed_message.content,
        )
        if interaction.message is not None:
            await interaction.message.edit(view=self.react_view)
        await interaction.response.defer(ephemeral=True)

class ReactDynamicSelectChannels(abc.ABC, discord.ui.ChannelSelect):
    def __init__(
            self, 
            *,
            react_view: _EditReactView, 
            custom_id: str,
            min_values: int = 1,
            max_values: int = 1,
            disabled: bool = False,
            placeholder: typing.Optional[str] = None,
            row: int = 0,
        ):
        self.config = react_view.config
        self.react_view = react_view

        super().__init__(
            custom_id=custom_id,
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            row=row,
            channel_types=[discord.ChannelType.text],
        )

    async def callback(self, interaction: discord.Interaction):
        self.react_view.config["channel_ids"] = [channel.id for channel in self.values]
        self.react_view.generate_prompt()
        await self.react_view.embed_message.edit(
            embed=ReactConfigurationEmbed(interaction.client, self.react_view.config),
            content=self.react_view.embed_message.content,
        )
        if interaction.message is not None:
            await interaction.message.edit(view=self.react_view)
        await interaction.response.defer(ephemeral=True)

class ReactSelectTriggerType(ReactDynamicSelect):
    def __init__(self, *, react_view: _EditReactView, row: int = 0):
        options = [
            discord.SelectOption(label=name, value=name.upper())
            for name in ReactType._member_names_
        ]

        for option in options:
            if (
                react_view.config["trigger"]["type"].value
                & ReactType._member_map_[option.value].value
            ):
                option.default = True

        super().__init__(
            react_view=react_view,
            custom_id="TRIGGER_TYPE",
            options=options,
            min_values=1,
            max_values=len(options),
            placeholder="Select one or more trigger types.",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.react_view.config["trigger"]["type"] = ReactType(0)
        for i in self.values:
            self.react_view.config["trigger"]["type"] |= ReactType._member_map_[i].value

        await super().callback(interaction)

class ReactSelectFromList(ReactDynamicSelect):
    def __init__(
        self,
        *,
        react_view: _EditReactView,
        custom_id: str,
        options: typing.List[discord.SelectOption],
        disabled: bool = False,
        max_values=1,
        min_values=1,
        placeholder="Select an option from the list.",
        row: int = 0,
    ):
        self.react_view = react_view
        super().__init__(
            max_values=max_values,
            min_values=min_values,
            placeholder=placeholder,
            react_view=react_view,
            custom_id=custom_id,
            options=options,
            row=row,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        print(f"I selected {', '.join(self.values)}")
        self.react_view.selection = self.values[0]
        await super().callback(interaction)
        pass

class ReactSelectYesNo(ReactDynamicSelect):
    def __init__(self, *, obj, key: typing.Union[str, int], react_view: _EditReactView, row: int = 0):

        self.obj = obj
        self.key = key

        options = [
            discord.SelectOption(label="Yes", value="True"),
            discord.SelectOption(label="No", value="False"),
        ]

        for option in options:
            if option.value == str(react_view.config["embed"] is not None and react_view.config["embed"]["use_embed"]):
                option.default = True

        super().__init__(
            react_view=react_view,
            custom_id=str(key).upper(),
            options=options,
            placeholder="Select Yes or No.",
            min_values=1,
            max_values=1,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        self.obj[self.key] = self.values[0] == "True"
        await super().callback(interaction)

class ReactSubmitButton(discord.ui.Button):
    def __init__(self, react_view: _EditReactView, row: int = 0):
        self.react_view = react_view
        super().__init__(label="Submit", style=discord.ButtonStyle.primary, row=row)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Finalizing...", ephemeral=True, delete_after=2
        )
        self.react_view.stop()

class EditReactTriggerView(_EditReactView):
    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(config, message)
        self.generate_prompt()

    def generate_prompt(self) -> None:
        super().generate_prompt()

        self.trigger_type: discord.ui.Select = ReactSelectTriggerType(
            react_view=self,
            row=0,
        )
        self.add_item(self.trigger_type)

        self.edit_chance: discord.ui.Button = ReactTextBasedModalButton(
            obj=self.config["trigger"],
            key="chance",
            react_view=self,
            label="Edit Trigger Chance",
            row=1,
            prompt_style=discord.TextStyle.short,
            placeholder="Enter a number between 0 and 1, or a diceroll like `1d30`.",
            required=True,
            converter=lambda s: s.replace(" ", "_").lower(),
            validation=validate_percent_or_diceroll,
        )
        self.add_item(self.edit_chance)

        if self.config["trigger"]["type"] & ReactType.MESSAGE:
            option_set = self.config["trigger"]["list"] or []

            options = [
                discord.SelectOption(
                    label=option_set[i][0:99], value=option_set[i][0:99]
                )
                for i in range(len(option_set))
            ]

            if len(option_set) > 0:
                if self.selection is None or self.selection not in option_set:
                    self.selection = option_set[0]
            
            if self.selection is not None:
                for option in options:
                    if option.value == self.selection[0:99]:
                        option.default = True

            self.trigger_select: ReactSelectFromList = ReactSelectFromList(
                react_view=self,
                custom_id="TRIGGER_SELECT",
                options=options,
                row=2,
                disabled=len(option_set) == 0,
            )

            self.add_trigger = ReactTextBasedModalButton(
                obj=self.config["trigger"]["list"],
                key=len(option_set),
                react_view=self,
                label="Add New Trigger",
                row=3,
                button_style=discord.ButtonStyle.success,
                prompt_style=discord.TextStyle.long,
                placeholder="Enter any phrase that will trigger a response.  Spaces and punctuation included.",
                converter=lambda s: s.lower(),
                validation=partial(validate_not_in_triggers, self.config["trigger"]["list"]),
            )
            self.add_item(self.add_trigger)

            self.edit_trigger: ReactTextBasedModalButton = ReactTextBasedModalButton(
                obj=self.config["trigger"]["list"],
                key=self.selection,
                button_style=discord.ButtonStyle.blurple,
                prompt_style=discord.TextStyle.long,
                required=True,
                react_view=self,
                disabled=self.selection == None,
                label=f"Edit Trigger",
                row=3,
                validation=partial(validate_not_in_triggers, self.config["trigger"]["list"]),
            )

            self.remove_trigger: ReactRemoveEntryButton = ReactRemoveEntryButton(
                obj=self.config["trigger"]["list"],
                key=self.selection,
                style=discord.ButtonStyle.danger,
                react_view=self,
                disabled=self.selection == None,
                label=f"Remove Trigger",
                row=3,
            )

            if len(option_set) > 0:
                self.add_item(self.trigger_select)
                self.add_item(self.edit_trigger)
                self.add_item(self.remove_trigger)

class EditReactEmbedView(_EditReactView):
    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(config, message)
        self.generate_prompt()
    
    def generate_prompt(self) -> None:
        super().generate_prompt()

        self.use_embed : ReactSelectYesNo = ReactSelectYesNo(
            obj=self.config["embed"],
            key="use_embed",
            react_view=self,
            row=0,
        )
        self.add_item(self.use_embed)

        self.edit_title: ReactTextBasedModalButton = ReactTextBasedModalButton(
            obj=self.config["embed"],
            key="title",
            react_view=self,
            label="Edit Embed Title",
            row=1,
            prompt_style=discord.TextStyle.long,
            placeholder="Enter a title for the embed.",
            validation=partial(validate_length, 256),
        )

        self.edit_footer: ReactTextBasedModalButton = ReactTextBasedModalButton(
            obj=self.config["embed"],
            key="footer",
            react_view=self,
            label="Edit Embed Footer",
            row=1,
            prompt_style=discord.TextStyle.long,
            placeholder="Enter a footer for the embed.",
            validation=partial(validate_length, 2048),
        )

        self.edit_color : ReactTextBasedModalButton = ReactTextBasedModalButton(
            obj=self.config["embed"],
            key="color",
            react_view=self,
            label="Edit Embed Color",
            row=2,
            prompt_style=discord.TextStyle.short,
            placeholder="Enter a color format, e.g. (255, 0, 0) or #FF0033.",
            converter=lambda s: convert_to_color(s).to_rgb(),
            validation=validate_color,
        )

        self.edit_image: ReactTextBasedModalButton = ReactTextBasedModalButton(
            obj=self.config["embed"],
            key="image_url",
            react_view=self,
            label="Edit Embed Image",
            row=2,
            prompt_style=discord.TextStyle.long,
            placeholder="Enter a URL for the embed image.",
            validation=validate_image,
        )

        if self.config["embed"] and self.config["embed"]["use_embed"]:
            self.add_item(self.edit_title)
            self.add_item(self.edit_color)
            self.add_item(self.edit_footer)
            self.add_item(self.edit_image)


class EditReactResponsesView(_EditReactView):
    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(config, message)
        self.generate_prompt()

    def generate_prompt(self) -> None:
        super().generate_prompt()

        option_set = self.config["responses"] or []

        options = [
            discord.SelectOption(
                label=option_set[i][0:99], value=option_set[i][0:99]
            )
            for i in range(len(option_set))
        ]

        if len(option_set) > 0:
            if self.selection is None or self.selection not in option_set:
                self.selection = option_set[0]

        if self.selection is not None:
            for option in options:
                if option.value == self.selection[0:99]:
                    option.default = True
        
        self.response_select: ReactSelectFromList = ReactSelectFromList(
            react_view=self,
            custom_id="RESPONSE_SELECT",
            options=options,
            disabled=len(option_set) == 0,
            row=2,
        )

        self.add_response = ReactTextBasedModalButton(
            obj=self.config["responses"],
            key=len(option_set),
            react_view=self,
            label="Add New Response",
            row=3,
            button_style=discord.ButtonStyle.success,
            prompt_style=discord.TextStyle.paragraph,
            placeholder="Enter a response the bot will provide to any listed trigger.",
        )
        self.add_item(self.add_response)

        self.edit_response : ReactTextBasedModalButton = ReactTextBasedModalButton(
            obj=self.config["responses"],
            key=self.selection,
            react_view=self,
            label=f"Edit Response",
            row=3,
            button_style=discord.ButtonStyle.blurple,
            prompt_style=discord.TextStyle.paragraph,
            placeholder=f"Enter a response the bot will provide to any listed trigger.",
        )

        self.remove_response : ReactRemoveEntryButton = ReactRemoveEntryButton(
            obj=self.config["responses"],
            key=self.selection,
            react_view=self,
            label=f"Remove Response",
            style=discord.ButtonStyle.danger,
            disabled=self.selection == None,
            row=3,
        )

        if len(options) > 0:
            self.add_item(self.response_select)
            self.add_item(self.edit_response)
            self.add_item(self.remove_response)
        pass



class EditReactOtherView(_EditReactView):
    def __init__(self, config: ReactConfig, message: discord.Message):
        super().__init__(config, message)
        self.config = config
        self.generate_prompt()

    def generate_prompt(self) -> None:
        super().generate_prompt()

        self.always_list: ReactDynamicSelectUsers = ReactDynamicSelectUsers(
            react_view=self,
            custom_id="ALWAYS_LIST",
            placeholder="Select users who will always trigger the response.",
            row=0,
            min_values=0,
            max_values=25,
        )
        self.add_item(self.always_list)

        self.channel_ids: ReactDynamicSelectChannels = ReactDynamicSelectChannels(
            react_view=self,
            custom_id="CHANNEL_IDS",
            placeholder="Select respond channels, or blank for all channels.",
            row=1,
            min_values=0,
            max_values=25,
        )
        self.add_item(self.channel_ids)

        self.submit : ReactSubmitButton = ReactSubmitButton(
            react_view=self,
            row=4,
        )
        self.add_item(self.submit)
        pass
