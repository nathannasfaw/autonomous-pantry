"""
LLM service: wraps Anthropic Claude calls for the Autonomous Pantry assistant.

Call 1: Intent + Recipe Discovery (with web search)
Call 2: Cart Narration
Call 3+: Conversation Loop
"""

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` fences and leading/trailing whitespace."""
    text = text.strip()
    # Remove ```json or ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text: str) -> dict | None:
    """
    Try to parse JSON from LLM response text.
    Returns None on failure.
    """
    cleaned = _strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from within the text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def _run_agentic_loop(system: str, user_message: str, tools: list | None = None) -> str:
    """
    Run the Anthropic API in an agentic loop until stop_reason == "end_turn".
    Handles tool use (web_search) automatically.
    Returns the final text content as a string.
    """
    client = _get_client()
    messages = [{"role": "user", "content": user_message}]

    kwargs = {
        "model": MODEL,
        "max_tokens": 4096,
        "system": system,
        "messages": messages,
    }
    if tools:
        kwargs["tools"] = tools

    accumulated_text = ""

    while True:
        response = client.messages.create(**kwargs)

        # Collect text blocks from this response
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                accumulated_text = block.text  # keep the latest text block

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            # web_search_20250305 is a server-side tool — Anthropic executes the search.
            # Just append the assistant turn and continue; do NOT send fake tool results
            # as that overrides the actual search results Anthropic provides.
            messages.append({"role": "assistant", "content": response.content})
            kwargs["messages"] = messages
        else:
            # Unexpected stop reason — break out
            break

    return accumulated_text


def call_llm_recipe(
    user_message: str,
    calendar: dict,
    preferences: dict,
    messages: list,
    pantry: list | None = None,
) -> dict:
    """
    LLM Call 1: Understand the user's dish request and either:
      - Present 2-3 recipe options (open-ended requests like "what can I make")
      - Search the web and return a full recipe (specific dish or user has chosen an option)
    """
    pantry_str = json.dumps(pantry or [])
    # Build a readable conversation history so the LLM knows if options were already shown
    history_str = json.dumps([
        {"role": m["role"], "content": m["content"]}
        for m in (messages or [])
        if m.get("role") in ("user", "assistant")
    ])

    system = f"""You are a grocery assistant. The user wants help deciding what to cook.

PANTRY (already owned — do NOT ask for this):
{pantry_str}

Calendar context: {json.dumps(calendar)}
User preferences: {json.dumps(preferences)}
Recent conversation: {history_str}

DECISION RULES — read the user's request carefully:

1. OPEN-ENDED request ("what can I make", "suggest something", "based on my pantry"):
   → Do NOT search the web yet.
   → Look at the pantry contents and preferences, then suggest 2-3 specific dishes they can make
     with minimal extra ingredients.
   → Return status "options_presented".

2. SPECIFIC dish request ("make tacos", "I want pasta") OR user is picking from options you already listed:
   → Use the web search tool to find a real recipe immediately. No questions.
   → Return status "recipe_found".

CRITICAL:
- NEVER ask what is in the pantry — it is provided above.
- NEVER ask clarifying questions.
- Return ONLY valid JSON. No markdown fences, no extra text.
- For serving size: use tonight_guests from calendar if set, otherwise 2.

For OPEN-ENDED requests return:
{{
  "message": "Friendly markdown message. List the options clearly using **bold** dish names. For each, mention what pantry items it uses and what 1-3 extra ingredients are needed.",
  "options": [
    {{"name": "Dish Name", "uses_from_pantry": ["item1", "item2"], "needs": ["extra1", "extra2"]}},
    {{"name": "Dish Name", "uses_from_pantry": ["item1"], "needs": ["extra1", "extra2", "extra3"]}},
    {{"name": "Dish Name", "uses_from_pantry": ["item1", "item2", "item3"], "needs": ["extra1"]}}
  ],
  "recipe": null,
  "status": "options_presented"
}}

For SPECIFIC dish requests or user selecting an option, search then return:
{{
  "message": "2-3 sentence markdown message. Bold the **recipe name**. Mention time and servings.",
  "options": null,
  "recipe": {{
    "name": "specific dish name",
    "servings": 2,
    "prep_time": "20 min",
    "cook_time": "25 min",
    "source_url": "url where recipe was found",
    "ingredients": [
      {{"item": "ingredient name", "quantity": 1.5, "unit": "lbs"}},
      ...
    ],
    "steps_summary": "brief 2-3 sentence summary of cooking steps"
  }},
  "status": "recipe_found"
}}"""

    try:
        raw_text = _run_agentic_loop(system, user_message, tools=[WEB_SEARCH_TOOL])
        parsed = _parse_json_response(raw_text)
        if parsed:
            return parsed
        else:
            logger.warning("Failed to parse recipe response. Raw: %r", raw_text[:300])
            return {
                "message": "I found a recipe for you! Let me set that up.",
                "options": None,
                "recipe": {
                    "name": user_message,
                    "servings": calendar.get("tonight_guests", 2),
                    "prep_time": "20 min",
                    "cook_time": "30 min",
                    "source_url": "",
                    "ingredients": [],
                    "steps_summary": "Cook and enjoy!",
                },
                "status": "recipe_found",
            }
    except Exception as e:
        logger.error(f"LLM Call 1 error: {e}")
        return {
            "message": "I had trouble with that request. Could you try again?",
            "options": None,
            "recipe": None,
            "status": "error",
        }


def call_llm_cart_narration(
    recipe: dict,
    pantry: list,
    gaps: list,
    nn_recommendations: list,
    preferences: dict,
    budget: float,
    cart_total: float = 0.0,
) -> dict:
    """
    LLM Call 2: Narrate the NN-generated cart in a friendly, conversational way.
    No web search needed.
    """
    system = f"""You are a friendly grocery assistant. A neural network has analyzed the user's pantry
and generated purchase recommendations. Your job is to present these clearly and conversationally.

Recipe: {json.dumps(recipe)}
Pantry state: {json.dumps(pantry)}
Ingredient gaps: {json.dumps(gaps)}
NN recommendations: {json.dumps(nn_recommendations)}
User preferences: {json.dumps(preferences)}
Budget: {budget}
Cart total (exact, computed from item prices — use this number, do NOT estimate): ${cart_total:.2f}

Return JSON only:
{{
  "message": "Use markdown formatting. Start with what the user already has in their pantry (if any), then clearly list what needs to be added. Use **bold** for item names. End with the exact cart total: ${cart_total:.2f}. Be concise but friendly.",
  "cart_summary": "one line summary of total items and cost",
  "status": "cart_proposed"
}}"""

    try:
        raw_text = _run_agentic_loop(system, "Please narrate the grocery cart for me.")
        parsed = _parse_json_response(raw_text)
        if parsed:
            return parsed
        else:
            total = sum(
                item.get("estimated_price", 0) * item.get("quantity", 1)
                for item in nn_recommendations
            )
            return {
                "message": f"Here's what I recommend adding to your cart based on your recipe and pantry! I've found {len(nn_recommendations)} items totaling about ${total:.2f}.",
                "cart_summary": f"{len(nn_recommendations)} items · ${total:.2f}",
                "status": "cart_proposed",
            }
    except Exception as e:
        logger.error(f"LLM Call 2 error: {e}")
        return {
            "message": "Here's your recommended cart based on what you need!",
            "cart_summary": f"{len(nn_recommendations)} items",
            "status": "cart_proposed",
        }


def call_llm_conversation(
    stage: str,
    current_cart: list,
    recipe: dict,
    preferences: dict,
    budget: float,
    messages: list,
) -> dict:
    """
    LLM Call 3+: Handle conversational turns — modifications, confirmations, questions.
    No web search needed.
    """
    # Format message history
    formatted_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
        if msg.get("role") in ("user", "assistant")
    ]

    # Get the last user message
    user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    system = f"""You are a friendly grocery assistant managing a grocery order through conversation.
You must detect the user's intent and return a structured JSON response.

Current stage: {stage}
Current cart: {json.dumps(current_cart)}
Recipe: {json.dumps(recipe)}
User preferences: {json.dumps(preferences)}
Budget: {budget}
Conversation history: {json.dumps(formatted_messages)}

Intent types:
- "modify": user wants to swap, add, remove, or change quantity of cart items
- "reset": user wants a completely different dish entirely
- "confirm": user is approving the order
- "cancel": user wants to stop
- "question": user is asking something, no cart change needed
- "unclear": you need to ask a clarifying question

Return JSON only:
{{
  "message": "Conversational response using markdown. Use **bold** for item names or key info. Keep it warm, direct, and clear. For modifications, confirm what changed. For confirmations, be enthusiastic. For questions, answer helpfully with structure if needed.",
  "intent": "modify | reset | confirm | cancel | question | unclear",
  "cart_diff": [
    {{"action": "swap", "from": "item_name", "to": "item_name", "quantity": 1.5, "unit": "lbs", "estimated_price": 16.00}},
    {{"action": "add", "item": "item_name", "quantity": 1, "unit": "pack", "estimated_price": 4.00}},
    {{"action": "remove", "item": "item_name"}},
    {{"action": "update_qty", "item": "item_name", "quantity": 2.0}}
  ],
  "new_intent": "pizza",
  "status": "negotiating | confirmed | cancelled | reset"
}}

If intent is "reset", cart_diff must be empty.
If intent is "confirm", set status to "confirmed".
Always respect dietary_flags from preferences — never add a conflicting item."""

    try:
        raw_text = _run_agentic_loop(system, user_message)
        parsed = _parse_json_response(raw_text)
        if parsed:
            return parsed
        else:
            return {
                "message": "I'm not sure I understood that. Could you clarify what you'd like to do with your cart?",
                "intent": "unclear",
                "cart_diff": [],
                "new_intent": "",
                "status": stage,
            }
    except Exception as e:
        logger.error(f"LLM Call 3 error: {e}")
        return {
            "message": "Something went wrong. Could you try again?",
            "intent": "unclear",
            "cart_diff": [],
            "new_intent": "",
            "status": stage,
        }
