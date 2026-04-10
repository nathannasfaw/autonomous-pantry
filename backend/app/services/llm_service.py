"""
LLM service: wraps Anthropic Claude calls for the Autonomous Pantry assistant.

Call 1: Intent + Recipe Discovery (with web search)
Call 2: Cart Narration
Call 3+: Conversation Loop
"""

from __future__ import annotations

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search"}

_client: anthropic.Anthropic | None = None

RECIPE_REQUEST_PATTERNS = [
    r"\brecipe\b",
    r"\brecipes\b",
    r"\bmeal ideas?\b",
    r"\bsuggest(?: me)?\b",
    r"\bwhat can i make\b",
    r"\bwhat should i cook\b",
    r"\bwhat can i cook\b",
    r"\bi want to make\b",
    r"\bi want to cook\b",
    r"\bfind me\b.*\brecipe\b",
    r"\bgive me\b.*\brecipe\b",
    r"\bdinner ideas?\b",
    r"\blunch ideas?\b",
    r"\bbreakfast ideas?\b",
    r"\bmeal suggestions?\b",
    r"\bcook with\b",
    r"\bmake with\b",
]

SCAN_UPDATE_PATTERNS = [
    r"\bscann?ed my pantry\b",
    r"\badded the following items\b",
    r"\bupdated my pantry\b",
    r"\bplease acknowledge this\b",
]

NORMALIZATION_PREFIXES = [
    r"^i want to make\s+",
    r"^i want to cook\s+",
    r"^make me\s+",
    r"^cook me\s+",
    r"^find me\s+(?:a|an)?\s*",
    r"^give me\s+(?:a|an)?\s*",
    r"^show me\s+(?:a|an)?\s*",
    r"^recipe for\s+",
    r"^recipes for\s+",
    r"^how do i make\s+",
    r"^how to make\s+",
]

TRAILING_FILLER_PATTERNS = [
    r"\s+recipe[s]?$",
    r"\s+for dinner$",
    r"\s+for lunch$",
    r"\s+for breakfast$",
    r"\s+please$",
    r"[.!?]+$",
]


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_json_response(text: str) -> dict | None:
    cleaned = _strip_markdown_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return None


def is_explicit_recipe_request(message: str) -> bool:
    normalized = message.lower().strip()
    if not normalized:
        return False

    if any(re.search(pattern, normalized) for pattern in SCAN_UPDATE_PATTERNS):
        return False

    return any(re.search(pattern, normalized) for pattern in RECIPE_REQUEST_PATTERNS)


def normalize_recipe_query(message: str) -> str:
    """
    Extract the likely dish name from a user request.
    Example: "I want to make pizza" -> "pizza"
    """
    normalized = message.lower().strip()
    for pattern in NORMALIZATION_PREFIXES:
        normalized = re.sub(pattern, "", normalized)
    for pattern in TRAILING_FILLER_PATTERNS:
        normalized = re.sub(pattern, "", normalized)

    normalized = re.sub(r"^(a|an|the)\s+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ,.-")
    return normalized or message.strip()


def _is_specific_recipe_request(message: str) -> bool:
    lowered = message.lower()
    open_ended_markers = [
        "what can i make",
        "what should i cook",
        "what can i cook",
        "meal ideas",
        "dinner ideas",
        "lunch ideas",
        "breakfast ideas",
        "suggest",
    ]
    return not any(marker in lowered for marker in open_ended_markers)


def _run_agentic_loop(system: str, user_message: str, tools: list | None = None) -> str:
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

        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                accumulated_text = block.text

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            kwargs["messages"] = messages
        else:
            break

    return accumulated_text


def _validate_recipe_payload(recipe: dict | None, normalized_query: str) -> tuple[bool, str]:
    if not recipe:
        return False, "missing recipe object"

    recipe_name = str(recipe.get("name", "")).strip()
    ingredients = recipe.get("ingredients") or []
    source_url = str(recipe.get("source_url", "")).strip()
    steps_summary = str(recipe.get("steps_summary", "")).strip()

    if not recipe_name:
        return False, "missing recipe name"
    if recipe_name.lower().strip() == normalized_query.lower().strip() and not ingredients:
        return False, "query echoed back without recipe details"
    if len(ingredients) < 3:
        return False, f"too few ingredients ({len(ingredients)})"
    if not source_url:
        return False, "missing source url"
    if not steps_summary:
        return False, "missing steps summary"

    return True, "ok"


def _build_recipe_failure(normalized_query: str, pantry: list | None, reason: str) -> dict:
    pantry_names = [item.get("item", "") for item in (pantry or []) if item.get("item")]
    pantry_preview = ", ".join(pantry_names[:5]) if pantry_names else "your current pantry"
    return {
        "message": (
            f"I couldn't find a solid **{normalized_query}** recipe to trust just yet. "
            f"I checked against {pantry_preview}. If you want, I can suggest a similar dish "
            f"or help you build a shopping list for **{normalized_query}**."
        ),
        "options": [
            {"name": f"{normalized_query} alternatives", "uses_from_pantry": pantry_names[:3], "needs": ["recipe retry"]},
        ],
        "recipe": None,
        "status": "recipe_lookup_failed",
        "failure_reason": reason,
        "normalized_query": normalized_query,
    }


def _attempt_recipe_lookup(
    *,
    system: str,
    user_input: str,
    normalized_query: str,
    pantry: list | None,
    retry_on_failure: bool,
) -> dict:
    raw_text = _run_agentic_loop(system, user_input, tools=[WEB_SEARCH_TOOL])
    parsed = _parse_json_response(raw_text)
    if not parsed:
        logger.warning(
            "Recipe response parse failed: normalized=%r retry=%s raw=%r",
            normalized_query,
            retry_on_failure,
            raw_text[:300],
        )
        if retry_on_failure:
            retry_system = system + """

RETRY INSTRUCTION:
- Your previous response was malformed or incomplete.
- Return exactly one valid JSON object.
- Do not include markdown fences.
- Do not omit recipe fields.
- If you cannot produce a valid recipe object, return status "recipe_lookup_failed".
"""
            return _attempt_recipe_lookup(
                system=retry_system,
                user_input=user_input,
                normalized_query=normalized_query,
                pantry=pantry,
                retry_on_failure=False,
            )
        return _build_recipe_failure(normalized_query, pantry, "unparseable_llm_response")

    parsed.setdefault("normalized_query", normalized_query)
    status = parsed.get("status")

    if status == "recipe_found":
        valid, reason = _validate_recipe_payload(parsed.get("recipe"), normalized_query)
        if not valid:
            logger.warning(
                "Recipe payload validation failed: normalized=%r retry=%s reason=%s payload=%r",
                normalized_query,
                retry_on_failure,
                reason,
                parsed.get("recipe"),
            )
            if retry_on_failure:
                retry_system = system + f"""

RETRY INSTRUCTION:
- Your previous recipe payload failed validation: {reason}
- Use the normalized dish query {json.dumps(normalized_query)}.
- Return a complete valid recipe object with a real source_url and at least 3 ingredients.
- If you cannot, return status "recipe_lookup_failed".
"""
                return _attempt_recipe_lookup(
                    system=retry_system,
                    user_input=user_input,
                    normalized_query=normalized_query,
                    pantry=pantry,
                    retry_on_failure=False,
                )
            return _build_recipe_failure(normalized_query, pantry, reason)

    logger.info(
        "Recipe lookup result: normalized=%r status=%s ingredients=%d retry=%s",
        normalized_query,
        status,
        len((parsed.get("recipe") or {}).get("ingredients") or []),
        retry_on_failure,
    )
    return parsed


def call_llm_recipe(
    user_message: str,
    calendar: dict,
    preferences: dict,
    messages: list,
    pantry: list | None = None,
) -> dict:
    pantry_str = json.dumps(pantry or [])
    history_str = json.dumps([
        {"role": m["role"], "content": m["content"]}
        for m in (messages or [])
        if m.get("role") in ("user", "assistant")
    ])
    normalized_query = normalize_recipe_query(user_message)
    specific_request = _is_specific_recipe_request(user_message)

    logger.info(
        "Recipe request received: original=%r normalized=%r pantry_items=%d specific=%s",
        user_message,
        normalized_query,
        len(pantry or []),
        specific_request,
    )

    system = f"""You are a grocery assistant. The user wants help deciding what to cook.

PANTRY (already owned - do NOT ask for this):
{pantry_str}

Calendar context: {json.dumps(calendar)}
User preferences: {json.dumps(preferences)}
Recent conversation: {history_str}
Normalized dish query: {json.dumps(normalized_query)}

DECISION RULES - read the user's request carefully:

0. ONLY start recipe flow if the user explicitly asks for a recipe, meal idea, or cooking suggestion.
   If the message is just a pantry update, acknowledgement, status note, or non-recipe chat,
   return status "not_recipe_request" with recipe null and options null.

1. OPEN-ENDED request ("what can I make", "suggest something", "based on my pantry"):
   -> Do NOT search the web yet.
   -> Look at the pantry contents and preferences, then suggest 2-3 specific dishes they can make
      with minimal extra ingredients.
   -> Return status "options_presented".

2. SPECIFIC dish request:
   -> Use the normalized dish query for web search.
   -> Search for one solid recipe only if you can provide a real recipe URL and a complete ingredient list.
   -> If you cannot find a trustworthy recipe, return status "recipe_lookup_failed".

CRITICAL:
- NEVER ask what is in the pantry - it is provided above.
- NEVER ask clarifying questions.
- NEVER echo the whole user phrase as the recipe name if it contains request words like "I want to make".
- For valid recipe_found results, recipe.name must be the dish name, not the raw user sentence.
- A valid recipe_found result MUST include:
  1. a normalized recipe name
  2. at least 3 ingredients
  3. a non-empty source_url
  4. a non-empty steps_summary
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
  "status": "options_presented",
  "normalized_query": {json.dumps(normalized_query)}
}}

For NON-RECIPE messages return:
{{
  "message": "Brief acknowledgement that no recipe flow was started.",
  "options": null,
  "recipe": null,
  "status": "not_recipe_request",
  "normalized_query": {json.dumps(normalized_query)}
}}

For FAILED SPECIFIC requests return:
{{
  "message": "Short apology that no trustworthy recipe was found. Offer a retry or a similar dish.",
  "options": [
    {{"name": "Similar Dish", "uses_from_pantry": ["item1"], "needs": ["extra1", "extra2"]}}
  ],
  "recipe": null,
  "status": "recipe_lookup_failed",
  "failure_reason": "short machine-readable reason",
  "normalized_query": {json.dumps(normalized_query)}
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
    "image_url": "url of a photo of the dish from the recipe page or search results. If none found, use empty string.",
    "ingredients": [
      {{"item": "ingredient name", "quantity": 1.5, "unit": "lbs"}},
      {{"item": "ingredient name", "quantity": 2, "unit": "cups"}},
      {{"item": "ingredient name", "quantity": 1, "unit": "tbsp"}}
    ],
    "steps_summary": "brief 2-3 sentence summary of cooking steps"
  }},
  "status": "recipe_found",
  "normalized_query": {json.dumps(normalized_query)}
}}"""

    try:
        return _attempt_recipe_lookup(
            system=system,
            user_input=normalized_query if specific_request else user_message,
            normalized_query=normalized_query,
            pantry=pantry,
            retry_on_failure=True,
        )
    except Exception as exc:
        logger.error("LLM Call 1 error for normalized=%r: %s", normalized_query, exc)
        return _build_recipe_failure(normalized_query, pantry, "llm_exception")


def call_llm_cart_narration(
    recipe: dict,
    pantry: list,
    gaps: list,
    nn_recommendations: list,
    preferences: dict,
    budget: float,
    cart_total: float = 0.0,
    staples_assumed: list | None = None,
) -> dict:
    staples_str = ", ".join(staples_assumed) if staples_assumed else "none"

    system = f"""You are a friendly grocery assistant. A neural network has analyzed the user's pantry
and generated purchase recommendations. Your job is to present these clearly and conversationally.

Recipe: {json.dumps(recipe)}
Pantry state: {json.dumps(pantry)}
Ingredient gaps: {json.dumps(gaps)}
NN recommendations: {json.dumps(nn_recommendations)}
User preferences: {json.dumps(preferences)}
Budget: {budget}
Cart total (exact, includes GA 4% sales tax + $4.99 delivery — use this number, do NOT estimate): ${cart_total:.2f}
Staples assumed on hand (filtered from cart): {staples_str}

Return JSON only:
{{
  "message": "Use markdown formatting. Keep it SHORT - 2-3 sentences max. Mention what key items they already have from their pantry. If staples were assumed on hand, briefly note them. Mention the total: ${cart_total:.2f} (which includes GA tax and delivery). Do NOT claim they already have everything unless the ingredient gaps list is empty and a valid recipe exists. Do NOT list every cart item individually — the user already sees those in a separate order card.",
  "cart_summary": "one line summary of total items and cost",
  "status": "cart_proposed"
}}"""

    try:
        raw_text = _run_agentic_loop(system, "Please narrate the grocery cart for me.")
        parsed = _parse_json_response(raw_text)
        if parsed:
            return parsed

        return {
            "message": f"Here's what I recommend adding to your cart! I've found {len(nn_recommendations)} items totaling ${cart_total:.2f} (including GA tax and delivery).",
            "cart_summary": f"{len(nn_recommendations)} items · ${cart_total:.2f}",
            "status": "cart_proposed",
        }
    except Exception as exc:
        logger.error("LLM Call 2 error: %s", exc)
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
    formatted_messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
        if msg.get("role") in ("user", "assistant")
    ]

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
Always respect dietary_flags from preferences - never add a conflicting item."""

    try:
        raw_text = _run_agentic_loop(system, user_message)
        parsed = _parse_json_response(raw_text)
        if parsed:
            return parsed
        return {
            "message": "I'm not sure I understood that. Could you clarify what you'd like to do with your cart?",
            "intent": "unclear",
            "cart_diff": [],
            "new_intent": "",
            "status": stage,
        }
    except Exception as exc:
        logger.error("LLM Call 3 error: %s", exc)
        return {
            "message": "Something went wrong. Could you try again?",
            "intent": "unclear",
            "cart_diff": [],
            "new_intent": "",
            "status": stage,
        }
