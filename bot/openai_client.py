from openai import OpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
)
from config import (
    OPENAI_API_KEY,
    FAQ_CONTENT,
    NOT_A_QUESTION_MARKER,
    CANNOT_ANSWER_MARKER,
)
from loguru import logger
import time
from typing import List, Union

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def get_llm_response(user_message: str, user_id: int = 0, chat_id: int = 0) -> str:
    """Get response from OpenAI using FAQ content."""
    start_time = time.time()
    logger.debug(
        "Processing LLM request",
        extra={
            "user_id": user_id,
            "message_preview": user_message[:100]
            + ("..." if len(user_message) > 100 else ""),
        },
    )

    if not client:
        logger.error("OpenAI client not initialized")
        return CANNOT_ANSWER_MARKER

    if not FAQ_CONTENT:
        logger.warning("FAQ content not available")
        return CANNOT_ANSWER_MARKER

    system_prompt = f"""You are a helpful AI assistant for students. Your knowledge is limited to the following FAQ:

--- BEGIN FAQ ---
{FAQ_CONTENT}
--- END FAQ ---

Instructions:
1. If the user's message is not a question (e.g., greetings, statements), respond with: {NOT_A_QUESTION_MARKER}
2. If the message is a question:
   - Answer briefly and clearly using only the FAQ (use bullet points if necessary), combining relevant parts if necessary.
   - Do not mention the FAQ in your answer.
   - If the question cannot be answered with the FAQ, respond with: {CANNOT_ANSWER_MARKER}

Ensure your response is in valid Markdown format, with proper syntax for *, _, `, [], and (). Be concise and helpful.
"""

    try:
        logger.debug("Sending request to OpenAI API", extra={"user_id": user_id})
        messages: List[
            Union[ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam]
        ] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_message),
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini", messages=messages, temperature=0.2, max_tokens=1000
        )

        response_text = completion.choices[0].message.content or CANNOT_ANSWER_MARKER
        response_text = response_text.strip()
        processing_time = time.time() - start_time

        response_type = (
            "not_question"
            if response_text == NOT_A_QUESTION_MARKER
            else "cannot_answer"
            if response_text == CANNOT_ANSWER_MARKER
            else "answered"
        )

        logger.info(
            "LLM response",
            extra={
                "response_type": response_type,
                "processing_time": round(processing_time, 2),
                "response_preview": response_text[:200]
                + ("..." if len(response_text) > 200 else ""),
            },
        )

        if hasattr(completion, "usage") and completion.usage:
            logger.debug(
                "Token usage",
                extra={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                },
            )

        return response_text

    except Exception as e:
        logger.exception("Error calling OpenAI", extra={"error": str(e)})
        return CANNOT_ANSWER_MARKER
