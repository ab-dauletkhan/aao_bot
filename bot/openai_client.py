from openai import OpenAI
from openai.types.chat import (
    ChatCompletionUserMessageParam,
    ChatCompletionSystemMessageParam,
)
from bot.config import (
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
    """Get response from OpenAI using FAQ content with enhanced logging and error handling."""
    start_time = time.time()

    # Enhanced context logging
    request_context = {
        "user_id": user_id,
        "chat_id": chat_id,
        "message_length": len(user_message),
        "message_preview": user_message[:100]
        + ("..." if len(user_message) > 100 else ""),
    }

    logger.debug("Processing LLM request", extra=request_context)

    # Client validation
    if not client:
        logger.error("OpenAI client not initialized", extra=request_context)
        return CANNOT_ANSWER_MARKER

    # FAQ validation
    if not FAQ_CONTENT:
        logger.warning("FAQ content not available", extra=request_context)
        return CANNOT_ANSWER_MARKER

    # Input validation
    if not user_message or not user_message.strip():
        logger.warning("Empty or whitespace-only message", extra=request_context)
        return NOT_A_QUESTION_MARKER

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
        logger.debug("Sending request to OpenAI API", extra=request_context)

        messages: List[
            Union[ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam]
        ] = [
            ChatCompletionSystemMessageParam(role="system", content=system_prompt),
            ChatCompletionUserMessageParam(role="user", content=user_message),
        ]

        # API call with timeout handling
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.2,
            max_tokens=1000,
            timeout=30.0,  # 30 second timeout
        )

        # Response validation and processing
        response_text = completion.choices[0].message.content

        if not response_text:
            logger.warning("OpenAI returned empty response", extra=request_context)
            return CANNOT_ANSWER_MARKER

        response_text = response_text.strip()

        if not response_text:
            logger.warning(
                "OpenAI returned whitespace-only response", extra=request_context
            )
            return CANNOT_ANSWER_MARKER

        processing_time = time.time() - start_time

        # Enhanced response classification
        response_type = _classify_response(response_text)

        # Enhanced logging with full context
        response_context = {
            **request_context,
            "response_type": response_type,
            "processing_time": round(processing_time, 2),
            "response_length": len(response_text),
            "response_preview": response_text[:200]
            + ("..." if len(response_text) > 200 else ""),
        }

        logger.info("LLM response generated", extra=response_context)

        # Token usage logging
        if hasattr(completion, "usage") and completion.usage:
            token_context = {
                **request_context,
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens,
            }
            logger.debug("Token usage", extra=token_context)

        return response_text

    except Exception as e:
        processing_time = time.time() - start_time
        error_context = {
            **request_context,
            "error": str(e),
            "error_type": type(e).__name__,
            "processing_time": round(processing_time, 2),
        }

        logger.exception("Error calling OpenAI API", extra=error_context)

        # Enhanced error handling based on error type
        if "timeout" in str(e).lower():
            logger.error("OpenAI API timeout", extra=error_context)
        elif "rate limit" in str(e).lower():
            logger.error("OpenAI API rate limit exceeded", extra=error_context)
        elif "authentication" in str(e).lower():
            logger.error("OpenAI API authentication failed", extra=error_context)
        elif "quota" in str(e).lower():
            logger.error("OpenAI API quota exceeded", extra=error_context)
        else:
            logger.error("Unknown OpenAI API error", extra=error_context)

        return CANNOT_ANSWER_MARKER


def _classify_response(response_text: str) -> str:
    """Classify the type of response for enhanced logging."""
    if response_text == NOT_A_QUESTION_MARKER:
        return "not_question"
    elif response_text == CANNOT_ANSWER_MARKER:
        return "cannot_answer"
    elif len(response_text.strip()) == 0:
        return "empty"
    else:
        return "answered"
