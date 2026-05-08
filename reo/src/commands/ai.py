# ai.py

import discord
from discord.ext import commands
import httpx
import traceback, sys

from reo.src.checks import checks
from reo.console.logging import logger
from reo.engine.Bot import AutoShardedBot
import storage


class AI(commands.Cog):
    def __init__(self, bot):
        self.bot: AutoShardedBot = bot
        class cog_info:
            name = "AI"
            category = "Extra"
            description = "Artificial Intelligence commands"
            hidden = False
            emoji = "🤖"
        self.cog_info = cog_info

    @commands.hybrid_command(
        name="ai",
        with_app_command=True,
        help="Ask AI a question",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=5, per=60, type=commands.BucketType.user)
    async def ai(self, ctx: commands.Context, *, question: str):
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.defer()

            if not ctx.guild:
                return await ctx.send("This command can only be used in a server.", ephemeral=True)

            # Get AI settings for this guild
            ai_settings = self.bot.cache.ai_settings.get(str(ctx.guild.id))
            
            if not ai_settings:
                return await ctx.send("AI is not configured for this server. Please ask an administrator to set it up in the dashboard.", ephemeral=True)
            
            if not ai_settings.get("enabled"):
                return await ctx.send("AI is disabled for this server.", ephemeral=True)
            
            api_base_url = ai_settings.get("api_base_url")
            api_key = ai_settings.get("api_key")
            max_tokens = ai_settings.get("max_tokens", 500)
            model = ai_settings.get("model") or "gpt-3.5-turbo"
            system_prompt = ai_settings.get("system_prompt")
            context_content = ai_settings.get("context_content")

            if not api_base_url or not api_key:
                return await ctx.send("AI is not properly configured. Missing API URL or Key.", ephemeral=True)

            # Build messages payload
            messages = []
            if system_prompt or context_content:
                sys_msg = ""
                if system_prompt: sys_msg += f"{system_prompt}\n\n"
                if context_content: sys_msg += f"Additional Context/Rules:\n{context_content}"
                messages.append({"role": "system", "content": sys_msg.strip()})
            messages.append({"role": "user", "content": question})

            # Call the AI API
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens
                }
                
                response = await client.post(
                    f"{api_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

            if response.status_code != 200:
                logger.error(f"AI API error: {response.status_code} - {response.text}")
                return await ctx.send(f"AI API returned an error: {response.status_code}", ephemeral=True)

            data = response.json()
            answer = data.get("choices", [{}])[0].get("message", {}).get("content", "No response received.")

            # Truncate if too long for Discord
            if len(answer) > 2000:
                answer = answer[:1997] + "..."

            embed = discord.Embed(
                title="🤖 AI Response",
                color=self.bot.color.DEFAULT,
            )
            embed.add_field(name="Question", value=question[:1024], inline=False)
            embed.add_field(name="Answer", value=answer, inline=False)
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

            await ctx.send(embed=embed)

        except httpx.TimeoutException:
            await ctx.send("AI request timed out. Please try again.", ephemeral=True)
        except Exception as e:
            logger.error(
                f"Error in file {__file__} at line {traceback.extract_tb(sys.exc_info()[2])[0][1]}: {e}"
            )
            await ctx.send("An error occurred while processing your request.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AI(bot))
