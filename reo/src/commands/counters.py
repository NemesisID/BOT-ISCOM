# counters.py

import discord
from discord.ext import commands
import traceback, sys
import asyncio

from reo.src.checks import checks
from reo.console.logging import logger
from reo.engine.Bot import AutoShardedBot
import storage


class Counters(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot
        class cog_info:
            name = "Counters"
            category = "Extra"
            description = "Automatic channel counters"
            hidden = False
            emoji = "📊"
        self.cog_info = cog_info
        self.task = None

    async def cog_load(self):
        self.task = asyncio.create_task(self._update_counters_loop())

    async def cog_unload(self):
        if self.task:
            self.task.cancel()

    async def _update_counters_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                await self._update_all_counters()
            except Exception as e:
                logger.error(f"Error updating counters: {e}")
            await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(minutes=5))

    async def _update_all_counters(self):
        for guild in self.bot.guilds:
            try:
                counter_config = self.bot.cache.counters.get(str(guild.id))
                if not counter_config or not counter_config.get("enabled"):
                    continue

                member_count = guild.member_count or 0
                bot_count = sum(1 for m in guild.members if m.bot)
                boost_count = guild.premium_subscription_count or 0

                everyone_role = guild.default_role

                async def _secure_channel(channel, new_name):
                    try:
                        await channel.edit(name=new_name)
                        perms = channel.overwrites_for(everyone_role)
                        if perms.connect != False or perms.view_channel != True:
                            perms.connect = False
                            perms.view_channel = True
                            await channel.set_permissions(everyone_role, overwrite=perms)
                    except discord.Forbidden:
                        pass

                # Update member counter
                member_channel_id = counter_config.get("member_counter_channel_id")
                if member_channel_id:
                    member_channel = guild.get_channel(member_channel_id)
                    if member_channel:
                        await _secure_channel(member_channel, f"📊〢Members: {member_count}")

                # Update bot counter
                bot_channel_id = counter_config.get("bot_counter_channel_id")
                if bot_channel_id:
                    bot_channel = guild.get_channel(bot_channel_id)
                    if bot_channel:
                        await _secure_channel(bot_channel, f"📊〢Bots: {bot_count}")

                # Update boost counter
                boost_channel_id = counter_config.get("boost_counter_channel_id")
                if boost_channel_id:
                    boost_channel = guild.get_channel(boost_channel_id)
                    if boost_channel:
                        await _secure_channel(boost_channel, f"📊〢Boosts: {boost_count}")

            except Exception as e:
                logger.error(f"Error updating counters for guild {guild.id}: {e}")

    @commands.group(
        name="counter",
        with_app_command=True,
        help="Manage automatic member counters",
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_channels=True)
    async def counter(self, ctx: commands.Context):
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer()

        counter_config = self.bot.cache.counters.get(str(ctx.guild.id)) or {}
        enabled = counter_config.get("enabled", False)
        status = "enabled" if enabled else "disabled"

        embed = discord.Embed(
            title="📊 Automatic Counters",
            color=self.bot.color.DEFAULT,
            description=f"Counter feature is currently **{status}**.\n\n"
            f"Use `/counter setup` to configure counters.\n"
            f"Use `/counter enable` or `/counter disable` to toggle.",
        )
        await ctx.send(embed=embed)

    @counter.command(
        name="enable",
        with_app_command=True,
        help="Enable automatic counters",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_channels=True)
    async def enable(self, ctx: commands.Context):
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer()

        counter_config = self.bot.cache.counters.get(str(ctx.guild.id))
        if not counter_config:
            counter_config = await storage.counters.insert(
                guild_id=ctx.guild.id,
                enabled=True,
            )
        else:
            await storage.counters.update(id=counter_config["id"], enabled=True)

        await ctx.send("✅ Automatic counters enabled. Configure channels in the dashboard or using `/counter setup`.")

    @counter.command(
        name="disable",
        with_app_command=True,
        help="Disable automatic counters",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_channels=True)
    async def disable(self, ctx: commands.Context):
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer()

        counter_config = self.bot.cache.counters.get(str(ctx.guild.id))
        if counter_config:
            await storage.counters.update(id=counter_config["id"], enabled=False)

        await ctx.send("✅ Automatic counters disabled.")

    @counter.command(
        name="setup",
        with_app_command=True,
        help="Setup counter channels",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_channels=True)
    async def setup(
        self,
        ctx: commands.Context,
        member_channel: discord.VoiceChannel = None,
        bot_channel: discord.VoiceChannel = None,
        boost_channel: discord.VoiceChannel = None,
    ):
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.defer()

        if not any([member_channel, bot_channel, boost_channel]):
            return await ctx.send("Please provide at least one channel to use as a counter.", ephemeral=True)

        counter_config = self.bot.cache.counters.get(str(ctx.guild.id))
        if not counter_config:
            counter_config = await storage.counters.insert(
                guild_id=ctx.guild.id,
                enabled=True,
                member_counter_channel_id=member_channel.id if member_channel else None,
                bot_counter_channel_id=bot_channel.id if bot_channel else None,
                boost_counter_channel_id=boost_channel.id if boost_channel else None,
            )
        else:
            await storage.counters.update(
                id=counter_config["id"],
                enabled=True,
                member_counter_channel_id=member_channel.id if member_channel else counter_config.get("member_counter_channel_id"),
                bot_counter_channel_id=bot_channel.id if bot_channel else counter_config.get("bot_counter_channel_id"),
                boost_counter_channel_id=boost_channel.id if boost_channel else counter_config.get("boost_counter_channel_id"),
            )

        # Update counters immediately
        await self._update_all_counters()

        await ctx.send("✅ Counter channels configured and updated!")


async def setup(bot):
    await bot.add_cog(Counters(bot))
