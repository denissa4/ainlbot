# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import os
import aiohttp
from botbuilder.core import (
    ActivityHandler,
    MessageFactory,
    TurnContext,
    CardFactory,
)
from botbuilder.schema import (
    Activity,
    ActivityTypes,
    CardAction,
    CardImage,
    HeroCard
)

class NLSQLBot(ActivityHandler):
    def __init__(self, nl_api_url: str, debug: bool = False):
        super(NLSQLBot, self).__init__()
        self.nl_api_url = nl_api_url
        self.debug = debug

        if self.debug:
            print(f"[DEBUG] Bot initialized with nl_api_url={nl_api_url}")

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity("Hello and welcome!")

    async def on_message_activity(self, turn_context: TurnContext):
        if self.debug:
            print("[DEBUG] Message received:", turn_context.activity.text)

        await self._send_typing_activity(turn_context)

        # Post to NLSQL API
        nlsql_answer = await self._api_post(
            channel_id=turn_context.activity.channel_id,
            text=turn_context.activity.text,
        )

        if self.debug:
            print("[DEBUG] NLSQL Answer:", nlsql_answer)

        answer_type = nlsql_answer.get("answer_type")
        answer = nlsql_answer.get("answer")
        unaccounted = nlsql_answer.get("unaccounted")
        addition_buttons = nlsql_answer.get("addition_buttons")
        buttons = nlsql_answer.get("buttons")
        images = nlsql_answer.get("images")
        card_data = nlsql_answer.get("card_data")

        # Handle different answer types
        if answer_type == "text":
            await self._text_answer(turn_context, answer)
        elif answer_type == "hero_card":
            await self._hero_card_answer(turn_context, answer, buttons, images)
        elif answer_type == "adaptive_card":
            await self._adaptive_card_answer(turn_context, card_data)
        else:
            await self._text_answer(turn_context, "NotImplemented")

        # Send any extra text or buttons
        if unaccounted:
            await self._text_answer(turn_context, unaccounted)

        if addition_buttons:
            await self._hero_card_answer(turn_context, "", addition_buttons, None)

    async def _send_typing_activity(self, turn_context: TurnContext):
        typing_activity = Activity(
            type=ActivityTypes.typing,
            channel_id=turn_context.activity.channel_id,
            conversation=turn_context.activity.conversation,
            recipient=turn_context.activity.from_property,
            from_property=turn_context.activity.recipient,
            service_url=turn_context.activity.service_url,
        )
        await turn_context.send_activity(typing_activity)

    async def _text_answer(self, turn_context: TurnContext, text: str):
        if self.debug:
            print("[DEBUG] Sending text:", text)
        await turn_context.send_activity(MessageFactory.text(text))

    async def _hero_card_answer(self, turn_context: TurnContext, text, buttons, images):
        if self.debug:
            print("[DEBUG] Sending Hero Card")

        images_list = []
        if images:
            for img in images:
                images_list.append(CardImage(url=img.get("img_url")))

        buttons_list = []
        if buttons:
            for btn in buttons:
                buttons_list.append(
                    CardAction(type=btn.get("type"), title=btn.get("title"), value=btn.get("value"))
                )
        card = HeroCard(
            title="",
            text=text,
            images=images_list,
            buttons=buttons_list,
        )

        attachment = CardFactory.hero_card(card)
        await turn_context.send_activity(MessageFactory.attachment(attachment))

    async def _adaptive_card_answer(self, turn_context: TurnContext, card_data):
        if self.debug:
            print("[DEBUG] Sending Adaptive Card")

        attachment = CardFactory.adaptive_card(card_data)
        await turn_context.send_activity(MessageFactory.attachment(attachment))

    async def _api_post(self, channel_id: str, text: str):
        body = {"channel_id": channel_id, "text": text}
        if self.debug:
            print("[DEBUG] Posting to API:", body)

        async with aiohttp.ClientSession() as session:
            async with session.post(self.nl_api_url, json=body) as response:
                result = await response.json()
                if self.debug:
                    print("[DEBUG] API response:", result)
                return result
