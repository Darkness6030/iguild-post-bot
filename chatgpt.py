from openai import OpenAI

from config import CHATGPT_API_KEY, CHATGPT_SYSTEM_PROMPT, CHATGPT_SETTINGS, CHATGPT_TRANSLATE_PROMPT

client = OpenAI(api_key=CHATGPT_API_KEY)


def generate_text(stats_text: str, text_length: int) -> str:
    completion = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": CHATGPT_SYSTEM_PROMPT.format(stats_text=stats_text, text_length=text_length)
        }],
        **CHATGPT_SETTINGS
    )
    return completion.choices[0].message.content


def translate_text(language: str, language_note: str, original_text: str) -> str:
    completion = client.chat.completions.create(
        messages=[{
            "role": "user",
            "content": CHATGPT_TRANSLATE_PROMPT.format(language=language, language_note=language_note, original_text=original_text)
        }],
        **CHATGPT_SETTINGS
    )

    return completion.choices[0].message.content
