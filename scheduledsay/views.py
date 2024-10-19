import asyncio
import datetime
import typing
import discord
from discord.utils import escape_markdown, escape_mentions
import dateparser  # type: ignore[import-untyped]
from croniter import croniter  # type: ignore[import-untyped]
from redbot.core.config import Config
from redbot.core.bot import Red

from dogscogs.constants import TIMEZONE, TIMEZONE_ID
from dogscogs.constants.discord.views import (
    MAX_SELECT_OPTIONS as DISCORD_MAX_SELECT_OPTIONS,
)
from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect
from dogscogs.views.confirmation import ConfirmationView

from .config import Schedule, create_schedule, ScheduleType, ScheduleDefinition
from . import scheduledsay
from .embed import ScheduledSayEmbed

DEFAULT_CONTENT = "<CONTENT>"
DEFAULT_TYPE: ScheduleType = "at"
DEFAULT_SCHEDULE: ScheduleDefinition = {
    "at": datetime.datetime.now(tz=TIMEZONE).timestamp(),
    "interval_secs": -1,
    "cron": "0 * * * *",
}

class CancelPrompt(discord.ui.View):
    def __init__(self, *args, author: discord.User, **kwargs):
        super().__init__(*args, **kwargs)

        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author.id

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()


class _ScheduleTypeModal(discord.ui.Modal):
    is_successful: bool = False

    def __init__(
        self,
        *args,
        schedule: Schedule,
        author_id: int,
        **kwars,
    ):
        super().__init__(*args, title="Scheduling", **kwars)

        self.author_id = author_id
        self.schedule = schedule

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                content="You are not the author of this schedule.",
                ephemeral=True,
            )
            return False

        return True

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()


class ScheduleCronTypeModal(_ScheduleTypeModal):
    cron_input: discord.ui.TextInput
    cron: typing.Union[str, None] = None

    def __init__(self, *args, schedule: Schedule, author_id: int, **kwargs):
        super().__init__(*args, schedule=schedule, author_id=author_id, **kwargs)

        self.cron_input = discord.ui.TextInput(
            custom_id="cron_input",
            placeholder="0 18 * * 0 (every Sunday at 6:00 PM)",
            row=0,
            required=True,
            default=(
                None
                if schedule["schedule"]["cron"] is None
                else schedule["schedule"]["cron"]
            ),
            label="Cron Expression (EST)",
            style=discord.TextStyle.long,
        )

        self.add_item(self.cron_input)

    async def interaction_check(self, interaction):
        try:
            cron = croniter(self.cron_input.value, start_time=datetime.datetime.now(tz=TIMEZONE))

            if cron.get_next(datetime.datetime) is None:
                raise ValueError("Invalid cron expression.")

            iter = cron.all_next(ret_type=datetime.datetime)

            next_one = next(iter)
            next_next_one = next(iter)

            if next_next_one - next_one < datetime.timedelta(seconds=60 * 60):
                await interaction.response.send_message(
                    content="Interval must be at least 1 hour.",
                    ephemeral=True,
                    delete_after=10,
                )
                return False

            self.cron = self.cron_input.value
        except:
            await interaction.response.send_message(
                content="Invalid cron expression provided.",
                ephemeral=True,
                delete_after=10,
            )
            return False

        return await super().interaction_check(interaction)

    async def on_submit(self, interaction: discord.Interaction):
        if await self.interaction_check(interaction):
            self.cron = self.cron_input.value
            self.is_successful = True

        await super().on_submit(interaction)


class ScheduleAtTypeModal(_ScheduleTypeModal):
    at_input: discord.ui.TextInput

    at: typing.Union[None, datetime.datetime] = None

    def __init__(
        self,
        *args,
        schedule: Schedule,
        author_id: int,
        **kwargs,
    ):
        super().__init__(*args, schedule=schedule, author_id=author_id, **kwargs)

        self.at_input = discord.ui.TextInput(
            custom_id="at_input",
            placeholder="2020-01-01T00:00:00 EST",
            row=0,
            required=True,
            default=(
                None
                if schedule["schedule"]["at"] is None
                else str(datetime.datetime.fromtimestamp(schedule["schedule"]["at"]))
            ),
            label="Timestamp or Datestring",
            style=discord.TextStyle.long,
        )

        self.add_item(self.at_input)

    async def interaction_check(self, interaction):
        try:
            dateparser.parse(self.at_input.value, settings={"TIMEZONE": TIMEZONE_ID})
        except:
            await interaction.response.send_message(
                content="Invalid datestring provided.",
                ephemeral=True,
                delete_after=10,
            )
            return False

        return await super().interaction_check(interaction)

    async def on_submit(self, interaction: discord.Interaction):
        if await self.interaction_check(interaction):
            self.at = dateparser.parse(
                self.at_input.value, settings={"TIMEZONE": TIMEZONE_ID}
            )
            self.is_successful = True

        await super().on_submit(interaction)


class ScheduleIntervalTypeModal(_ScheduleTypeModal):
    at_input: discord.ui.TextInput
    interval_input: discord.ui.TextInput

    at: typing.Union[None, datetime.datetime] = None
    interval_secs: typing.Union[None, int] = None

    def __init__(
        self,
        *args,
        schedule: Schedule,
        author_id: int,
        **kwargs,
    ):
        super().__init__(*args, schedule=schedule, author_id=author_id, **kwargs)

        self.at_input = discord.ui.TextInput(
            custom_id="at_input",
            placeholder="2020-01-01T00:00:00 EST",
            row=0,
            required=True,
            default=(
                None
                if schedule["schedule"]["at"] is None
                else str(datetime.datetime.fromtimestamp(schedule["schedule"]["at"]))
            ),
            label="Next Occurrence",
            style=discord.TextStyle.long,
        )

        self.interval_input = discord.ui.TextInput(
            custom_id="interval_input",
            placeholder="1d",
            row=1,
            required=True,
            default=(
                None
                if schedule["schedule"]["interval_secs"] is None
                else str(schedule["schedule"]["interval_secs"])
            ),
            label="Interval (Seconds)",
            style=discord.TextStyle.short,
        )

        self.add_item(self.at_input)
        self.add_item(self.interval_input)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        try:
            dateparser.parse(self.at_input.value, settings={"TIMEZONE": TIMEZONE_ID})
        except:
            await interaction.response.send_message(
                content="Invalid datestring provided for `Next Occurrence`.",
                ephemeral=True,
                delete_after=10,
            )
            return False

        try:
            try:
                if int(self.interval_input.value) < 60 * 60:
                    await interaction.response.send_message(
                        content="Interval must be at least 1 hour.",
                        ephemeral=True,
                        delete_after=10,
                    )
                    return False

                self.interval_secs = int(self.interval_input.value)
            except:
                try:
                    cron = croniter(self.interval_input.value, start_time=datetime.datetime.now(tz=TIMEZONE))

                    if cron.is_valid() is False:
                        raise ValueError("Invalid cron expression.")

                    iter: typing.Iterator[datetime.datetime] = cron.all_next(
                        ret_type=datetime.datetime
                    )
                    next_one = next(iter)
                    next_next_one = next(iter)

                    if next_next_one - next_one < datetime.timedelta(seconds=60 * 60):
                        raise ValueError("Interval must be at least 1 hour.")

                    self.interval_secs = int((next_one - next_next_one).total_seconds())

                except:
                    date = dateparser.parse(
                        self.interval_input.value, settings={"TIMEZONE": TIMEZONE_ID}
                    )

                    if date - datetime.datetime.now() < datetime.timedelta(
                        seconds=60 * 60
                    ):
                        raise ValueError("Interval must be at least 1 hour.")

                    self.interval_secs = (
                        date - datetime.datetime.now()
                    ).total_seconds()
        except:
            await interaction.response.send_message(
                content="Invalid interval provided.",
                ephemeral=True,
                delete_after=10,
            )
            return False

        return await super().interaction_check(interaction)

    async def on_submit(self, interaction: discord.Interaction):
        if await self.interaction_check(interaction):
            self.at = dateparser.parse(
                self.at_input.value, settings={"TIMEZONE": TIMEZONE_ID}
            )
            self.is_successful = True

        await super().on_submit(interaction)


class ScheduledSayListPaginatedEmbed(PaginatedEmbed):
    config: Config
    guild: discord.Guild
    schedule: Schedule

    select_list: typing.Optional[OnCallbackSelect] = None

    def __init__(
        self,
        *args,
        bot: Red,
        config: Config,
        interaction: typing.Optional[discord.Interaction] = None,
        original_message: typing.Optional[discord.Message] = None,
        filter: typing.Callable[[Schedule], bool] = lambda m: True,
        **kwargs,
    ):
        if interaction is None and original_message is None:
            raise ValueError("Either interaction or original_message must be provided.")

        async def get_page(index: int) -> typing.Tuple[discord.Embed, int]:
            schedules: typing.List[Schedule] = await self.config.guild(
                self.guild
            ).schedules()
            filtered_schedules = [s for s in schedules if filter(s)]

            if not filtered_schedules or len(filtered_schedules) == 0:
                return (
                    discord.Embed(
                        title="No Schedules Found",
                        description="There are no schedules to display.",
                        color=discord.Color.red(),
                    ),
                    1,
                )

            self.schedule = filtered_schedules[index]

            return await ScheduledSayEmbed(
                config=self.config,
                guild=self.guild,
                schedule_id=filtered_schedules[index]["id"],
            ).send(), len(filtered_schedules)

        super().__init__(
            *args,
            interaction=interaction,
            message=original_message,
            get_page=get_page,
            **kwargs,
        )

        self.bot = bot
        self.config = config
        self.guild = self.interaction.guild if self.interaction else self.original_message.guild  # type: ignore[assignment,union-attr]
        self.filter = filter

    async def edit_page(self) -> None:
        _, size = await self.get_page(0)

        self.edit.disabled = False
        self.delete.disabled = False
        self.previous.disabled = False
        self.next.disabled = False

        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        filtered_schedules = [s for s in schedules if self.filter(s)]

        if size > 1 and size < DISCORD_MAX_SELECT_OPTIONS:

            async def edit_selected_page(values: typing.List[str]) -> None:
                self.index = int(values[0])
                await self.edit_page()

            options = [
                discord.SelectOption(
                    label=f"{escape_markdown(escape_mentions(schedule['content']))[:20]}{'...' if len(escape_markdown(escape_mentions(schedule['content']))) > 20 else ''}",
                    value=str(i),
                    default=True if i == self.index else False,
                )
                for i, schedule in enumerate(filtered_schedules)
            ]

            if self.select_list is None:
                self.select_list: OnCallbackSelect = OnCallbackSelect(
                    custom_id="schedule_list",
                    placeholder="Select a scheduled message",
                    options=options,
                    callback=edit_selected_page,
                    row=1,
                    max_values=1,
                    min_values=1,
                )
                self.add_item(self.select_list)
            else:
                self.select_list.options = options

        elif size <= 1:
            if self.select_list is not None:
                self.remove_item(self.select_list)
                self.select_list = None
            self.previous.disabled = True
            self.next.disabled = True

            if len(filtered_schedules) == 0:
                self.edit.disabled = True
                self.delete.disabled = True

        await super().edit_page()

    async def send(self) -> "ScheduledSayListPaginatedEmbed":
        await super().send()

        self.update_buttons()
        await self.edit_page()
        await self.message.edit(view=self)

        return self

    @discord.ui.button(label="Add New", style=discord.ButtonStyle.primary, row=2)
    async def add_new(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()

        new_schedule = create_schedule(
            channel_ids=[],
            is_active=False,
            author_id=interaction.user.id,
            content=DEFAULT_CONTENT,
            type=DEFAULT_TYPE,
            schedule=DEFAULT_SCHEDULE,
        )

        schedules.append(new_schedule)

        await self.config.guild(self.guild).schedules.set(schedules)

        self.index = len([s for s in schedules if self.filter(s)]) - 1

        await self.edit_page()

        await interaction.response.defer()
        pass

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary, row=2)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        view = await ScheduledSayConfigure(
            bot=self.bot,
            config=self.config,
            guild=self.guild,
            message=self.message,
            schedule_id=self.schedule["id"],
            author_id=interaction.user.id,
        ).collect()

        await self.message.edit(view=view)
        await view.wait()

        await scheduledsay.ScheduledSay.schedule_message(
            self.config, self.guild, self.schedule["id"]
        )

        await self.edit_page()
        pass

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=2)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        i, schedule = next(
            ((i, s) for i, s in enumerate(schedules) if s["id"] == self.schedule["id"]),
            (None, None),
        )

        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        view = ConfirmationView(author=interaction.user)  # type: ignore[arg-type]

        await interaction.response.send_message(
            content=f"Are you sure you want to delete the schedule `{schedule['id']}`?",
            view=view,
            ephemeral=True,
        )

        if await view.wait() or not view.value:
            await interaction.delete_original_response()
            return

        schedule["is_active"] = False
        schedules[i] = schedule  # type: ignore[index]
        await self.config.guild(self.guild).schedules.set(schedules)

        await scheduledsay.ScheduledSay.schedule_message(self.config, self.guild, schedule["id"])

        schedules.pop(i)  # type: ignore[arg-type]

        await self.config.guild(self.guild).schedules.set(schedules)

        await interaction.delete_original_response()

        self.index = max(self.index - 1, 0)

        await self.edit_page()


class ScheduledSayConfigure(discord.ui.View):
    type_select: typing.Union[None, OnCallbackSelect] = None

    def __init__(
        self,
        bot: Red,
        config: Config,
        guild: discord.Guild,
        message: discord.Message,
        author_id: int,
        schedule_id: str,
    ):
        super().__init__()

        self.bot = bot
        self.config = config
        self.guild = guild
        self.message = message
        self.author_id = author_id
        self.schedule_id = schedule_id

    async def collect(self) -> "ScheduledSayConfigure":
        self.clear_items()

        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        schedule = next((s for s in schedules if s["id"] == self.schedule_id), None)

        if schedule is None:
            raise ValueError(f"No schedule found for the given id: {self.schedule_id}")

        if not schedule["is_active"]:
            self.toggle_active.label = "Set Active"
            self.toggle_active.style = discord.ButtonStyle.success
        else:
            self.toggle_active.label = "Set Inactive"
            self.toggle_active.style = discord.ButtonStyle.danger

        async def update_trigger_type(values: typing.List[str]) -> None:
            schedules: typing.List[Schedule] = await self.config.guild(
                self.guild
            ).schedules()
            i, schedule = next(
                (
                    (i, s)
                    for i, s in enumerate(schedules)
                    if s["id"] == self.schedule_id
                ),
                (None, None),
            )

            if schedule is None:
                raise ValueError("No schedule found for the given id.")

            schedule["type"] = values[0]  # type: ignore[typeddict-item]
            schedules[i] = schedule  # type: ignore[index]
            await self.config.guild(self.guild).schedules.set(schedules)

            await self.collect()

        self.type_select: OnCallbackSelect = OnCallbackSelect(
            custom_id="schedule_type",
            placeholder="Select a Trigger Type",
            options=[
                discord.SelectOption(
                    label="At Specific Time",
                    value="at",
                    default=True if schedule["type"] == "at" else False,
                ),
                discord.SelectOption(
                    label="Every X",
                    value="every",
                    default=True if schedule["type"] == "every" else False,
                ),
                discord.SelectOption(
                    label="Cron Expression",
                    value="cron",
                    default=True if schedule["type"] == "cron" else False,
                ),
            ],
            row=1,
            max_values=1,
            min_values=1,
            callback=update_trigger_type,
        )

        self.add_item(self.toggle_active)
        self.add_item(self.edit_content)
        self.add_item(self.type_select)
        self.add_item(self.edit_schedule)
        self.add_item(self.channel_select)
        self.add_item(self.finish)

        await self.message.edit(
            embed=await ScheduledSayEmbed(
                self.config, self.guild, self.schedule_id
            ).send(),
            view=self,
        )

        return self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                content="You are not the author of this schedule.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(label="Set Inactive", style=discord.ButtonStyle.success, row=0)
    async def toggle_active(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        i, schedule = next(
            ((i, s) for i, s in enumerate(schedules) if s["id"] == self.schedule_id),
            (None, None),
        )

        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        schedule["is_active"] = not schedule["is_active"]
        schedules[i] = schedule  # type: ignore[index]
        await self.config.guild(self.guild).schedules.set(schedules)

        await scheduledsay.ScheduledSay.schedule_message(self.config, self.guild, self.schedule_id)

        await interaction.response.defer()

        await self.collect()

        pass

    @discord.ui.button(label="Edit Content", style=discord.ButtonStyle.primary, row=0)
    async def edit_content(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        cancel_button = CancelPrompt(author=interaction.user, timeout=300) # type: ignore[arg-type]

        wait_message = await interaction.channel.send(  # type: ignore[union-attr]
            "Awaiting new content for the message...",
            view = cancel_button
        )

        events = [
            asyncio.create_task(self.bot.wait_for("message", check=lambda m: m.author.id == self.author_id, timeout=300)),
            asyncio.create_task(self.bot.wait_for('interaction', check=lambda i: i.message.id == wait_message.id, timeout=300))
        ]

        try:
            done, pending = await asyncio.wait(events, return_when=asyncio.FIRST_COMPLETED)
            event = done.pop().result()

            for future in pending:
                future.cancel()

        except asyncio.TimeoutError:
            await wait_message.delete()
            await interaction.channel.send("Timed out waiting for new content.", delete_after=10)  # type: ignore[union-attr]
            return
        
        await wait_message.delete()

        if isinstance(event, discord.Interaction):
            await interaction.channel.send("Canceled.", delete_after=5)  # type: ignore[union-attr]
            return
        else:
            message : discord.Message = event

        view = ConfirmationView(author=message.author) # type: ignore[arg-type]
        prompt = await interaction.channel.send(f"Set content to the following?\n\n{message.content}", view=view, allowed_mentions=discord.AllowedMentions.none())  # type: ignore[union-attr]

        if await view.wait() or not view.value:
            await prompt.delete()
            return

        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        i, schedule = next(
            ((i, s) for i, s in enumerate(schedules) if s["id"] == self.schedule_id),
            (None, None),
        )
        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        schedule["content"] = message.content
        schedules[i] = schedule  # type: ignore[index]
        await self.config.guild(self.guild).schedules.set(schedules)

        await prompt.delete()

        await self.collect()
        pass

    @discord.ui.button(label="Edit Schedule", style=discord.ButtonStyle.primary, row=2)
    async def edit_schedule(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):

        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        i, schedule = next(
            ((i, s) for i, s in enumerate(schedules) if s["id"] == self.schedule_id),
            (None, None),
        )

        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        modal: _ScheduleTypeModal

        if schedule["type"] == "at":
            modal = ScheduleAtTypeModal(
                schedule=schedule,
                author_id=self.author_id,
            )
            pass
        elif schedule["type"] == "every":
            modal = ScheduleIntervalTypeModal(
                schedule=schedule,
                author_id=self.author_id,
            )
            pass
        elif schedule["type"] == "cron":
            modal = ScheduleCronTypeModal(
                schedule=schedule,
                author_id=self.author_id,
            )
            pass

        await interaction.response.send_modal(modal)
        if await modal.wait() or not modal.is_successful:
            return

        if schedule["type"] == "cron":
            schedule["schedule"]["cron"] = modal.cron  # type: ignore[attr-defined]
        elif schedule["type"] == "at":
            schedule["schedule"]["at"] = modal.at.timestamp()  # type: ignore[attr-defined]
        elif schedule["type"] == "every":
            schedule["schedule"]["at"] = modal.at.timestamp()  # type: ignore[attr-defined]
            schedule["schedule"]["interval_secs"] = modal.interval_secs  # type: ignore[attr-defined]

        schedules[i] = schedule  # type: ignore[index]
        await self.config.guild(self.guild).schedules.set(schedules)

        await scheduledsay.ScheduledSay.schedule_message(self.config, self.guild, self.schedule_id)

        await self.collect()
        pass

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.private_thread],
        custom_id="schedule_channel",
        placeholder="Select a Channel",
        row=3,
        max_values=DISCORD_MAX_SELECT_OPTIONS,
        min_values=0,
    )
    async def channel_select(
        self, interaction: discord.Interaction, select: discord.ui.ChannelSelect
    ):
        await interaction.response.defer()

        schedules: typing.List[Schedule] = await self.config.guild(
            self.guild
        ).schedules()
        i, schedule = next(
            ((i, s) for i, s in enumerate(schedules) if s["id"] == self.schedule_id),
            (None, None),
        )

        if schedule is None:
            raise ValueError("No schedule found for the given id.")

        schedule["channel_ids"] = [v.id for v in select.values]
        schedules[i] = schedule  # type: ignore[index]
        await self.config.guild(self.guild).schedules.set(schedules)

        await self.collect()

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.success, row=4)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()
        pass
