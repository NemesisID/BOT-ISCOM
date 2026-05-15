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

    async def _try_ai_request(self, api_base_url: str, api_key: str, model: str, messages: list, max_tokens: int):
        async with httpx.AsyncClient() as client:
            headers_openai = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload_openai = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens
            }

            target_url = f"{api_base_url.rstrip('/')}/chat/completions"
            logger.info(f"[AI] Trying OpenAI endpoint: {target_url} with model: {model}")

            try:
                response = await client.post(
                    target_url,
                    headers=headers_openai,
                    json=payload_openai,
                    timeout=30.0
                )
            except Exception as e:
                logger.error(f"[AI] OpenAI request exception: {e}")
                response = None

            if response is not None and response.status_code == 200:
                return response

            logger.warning(f"[AI] OpenAI endpoint failed (status {response.status_code if response else 'None'}). Trying Anthropic protocol fallback...")

            anthropic_messages = []
            anthropic_system = None

            for msg in messages:
                if msg.get("role") == "system":
                    anthropic_system = msg.get("content")
                else:
                    anthropic_messages.append({
                        "role": msg.get("role"),
                        "content": msg.get("content")
                    })

            headers_anthropic = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload_anthropic = {
                "model": model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens
            }
            if anthropic_system:
                payload_anthropic["system"] = anthropic_system

            anthropic_url = f"{api_base_url.rstrip('/')}/messages"
            logger.info(f"[AI] Trying Anthropic endpoint: {anthropic_url}")

            try:
                response_anthropic = await client.post(
                    anthropic_url,
                    headers=headers_anthropic,
                    json=payload_anthropic,
                    timeout=30.0
                )
                if response_anthropic.status_code == 200:
                    return response_anthropic
                logger.error(f"[AI] Anthropic fallback failed: {response_anthropic.status_code} - {response_anthropic.text}")
                return response_anthropic
            except Exception as e:
                logger.error(f"[AI] Anthropic request exception: {e}")
                return response

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

            # Call the AI API with typing status
            async with ctx.typing():
                response = await self._try_ai_request(api_base_url, api_key, model, messages, max_tokens)

                # If primary model failed with capacity/404, retry with fallback model
                if response is None or response.status_code != 200:
                    fallback_model = ai_settings.get("fallback_model")
                    if fallback_model and fallback_model != model:
                        logger.warning(f"[AI] Primary model '{model}' unavailable, trying fallback '{fallback_model}'")
                        response = await self._try_ai_request(api_base_url, api_key, fallback_model, messages, max_tokens)

            if response is None or response.status_code != 200:
                status_code = response.status_code if response else "Unknown"
                resp_text = response.text if response else "No response"
                logger.error(f"AI API error: {status_code} - {resp_text}")

                if status_code in (404, 503, 529):
                    user_msg = "AI provider sedang tidak tersedia atau model sedang sibuk. Silakan coba lagi nanti."
                elif status_code == 429:
                    user_msg = "AI rate limit tercapai. Silakan tunggu beberapa saat dan coba lagi."
                else:
                    user_msg = f"AI API error ({status_code}). Silakan coba lagi nanti."

                return await ctx.send(user_msg, ephemeral=True)

            data = response.json()
            # Parse content based on which protocol succeeded
            if "choices" in data:
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "No response received.")
            elif "content" in data and isinstance(data["content"], list):
                # Anthropic format
                text_parts = [part.get("text", "") for part in data["content"] if part.get("type") == "text"]
                answer = "".join(text_parts) or "No response received."
            else:
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

    @commands.hybrid_command(
        name="aimodels",
        with_app_command=True,
        help="List available AI models from the configured provider",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    async def aimodels(self, ctx: commands.Context):
        try:
            if ctx.interaction and not ctx.interaction.response.is_done():
                await ctx.defer()

            if not ctx.guild:
                return await ctx.send("This command can only be used in a server.", ephemeral=True)

            ai_settings = self.bot.cache.ai_settings.get(str(ctx.guild.id))
            if not ai_settings:
                return await ctx.send("AI is not configured for this server.", ephemeral=True)

            api_base_url = ai_settings.get("api_base_url")
            api_key = ai_settings.get("api_key")

            if not api_base_url or not api_key:
                return await ctx.send("AI is not properly configured. Missing API URL or Key.", ephemeral=True)

            async with ctx.typing():
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    }
                    response = await client.get(
                        f"{api_base_url.rstrip('/')}/models",
                        headers=headers,
                        timeout=10.0
                    )

            if response.status_code != 200:
                logger.error(f"[AI Models Debug] Error: {response.status_code} - {response.text}")
                return await ctx.send(f"Failed to fetch models: {response.status_code}", ephemeral=True)

            data = response.json()
            models_list = [m.get("id") for m in data.get("data", [])]
            models_str = ", ".join(models_list)
            
            logger.info(f"[AI Models Debug] Supported models: {models_str}")
            
            if not models_str:
                return await ctx.send("No models returned by the provider.", ephemeral=True)

            # Send list to chat, truncate if too long
            if len(models_str) > 1900:
                models_str = models_str[:1900] + "..."
                
            await ctx.send(f"**Available Models on x5LAB:**\n`{models_str}`")

        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            await ctx.send("An error occurred while fetching models.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(AI(bot))
