import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_OWNER_ID = int(os.getenv("BOT_OWNER_ID"))
WATCH_CHANNEL_ID = int(os.getenv("WATCH_CHANNEL_ID"))

CHATGPT_API_KEY = os.getenv("CHATGPT_API_KEY")

CHATGPT_SYSTEM_PROMPT = """
Проанализируй данные.

{stats_text}

В прогнозах опирайся именно на коэффициенты, а не на время. Минимальное значение коэффициента 1.
::
Скользящая средняя показывает какой процент коэффициентов, за последние 5 шагов от точки анализа, был выше 1.7.
::
Выступи в роли эксперта по техническому анализу. Анализируя скользящую среднюю из данных выше. Выбери самые крупные числа на таймфейме и опиши, что было перед ними. Дай комментарий, к тому, что стало дальше и почему. Без визуализаций, без вступлений, только сухой прогноз на будущее.
::
В прогнозах не пиши "рынок", используй термин "игра".
::
Задача поймать коэффициент выше 1.7, а ещё лучше выше 8.2, дай понять где ставить для этого.
::
Оформи в виде поста для телеграм канала, с эмоджи но без заголовка.
::
Длина не более {text_length} символов. 
::
Будь ближе к читателю, обращайся на ТЫ.
::
Используй сленг трейдеров и игроков онлайн казино.
"""

CHATGPT_TRANSLATE_PROMPT = """
Переведи текст на {language}. {language_note}
::
Переводи натурально, будь ближе к читателю, используй сленг трейдеров и игроков онлайн казино.
::
Максимально сохраняй оригинальный стиль, эмодзи и форматирование.
::
Выводи только переведённый текст и ничего больше.
::
Текст: {original_text}
"""

CHATGPT_SETTINGS = dict(
    model="gpt-4o"
)

PUBLISH_POST_BUTTON = "✅ Опубликовать"
EDIT_POST_BUTTON = "✏️ Отредактировать"
DELETE_POST_BUTTON = "❌ Отменить"

POST_PUBLISHED_TEXT = "✅ Пост опубликован."
POST_DELETED_TEXT = "❌ Пост отменён."

WINS_POST_TEXT = "📊 Заносы за последний час:"
EDIT_POST_TEXT = "📄 Пожалуйста, введите текст или отправьте голосовое сообщение для редактирования поста:"
INVALID_EDIT_TEXT = "❌ Редактирование поста поддерживает только текст или голосовые сообщения. Попробуйте ещё раз:"

ADMIN_SETTINGS_TEXT = "Выберите, что хотите переключить:"
MODERATION_BUTTON = "{status} Модерация постов"
GENERATION_BUTTON = "{status} Генерация постов"

INVALID_MESSAGE_URL_TEXT = "❌ Некорректная ссылка на сообщение."
BUTTON_EDITED_TEXT = "✏️ Кнопка успешно отредактирована."
BUTTON_DELETED_TEXT = "✏️ Кнопка успешно удалена."
BUTTON_NOT_EDITED_TEXT = "❌ Не удалось отредактировать сообщение.\n<code>{error}</code>"

WIN_EMOJIS = "✅💪🎉👏🔥🤘🚀🥳💎"
WIN_BIG_PERCENT = 10000

TEXT_LENGTHS = {
    160: 0.5,
    250: 0.3,
    350: 0.15,
    600: 0.05
}


class State(BaseModel):
    moderation_enabled: bool = True
    generation_enabled: bool = True
    current_link_index: dict[int, int] = {}
    last_600_usage_date: str = ""


def load_state(filename="state.json") -> State:
    if not os.path.exists(filename):
        return State()

    with open(filename, "r") as file:
        return State.model_validate_json(file.read())


def save_state(state: State, filename="state.json"):
    with open(filename, "w") as file:
        file.write(state.model_dump_json())


class Channel(BaseModel):
    language: str
    language_note: str = ""
    utm_source: str
    channel_id: int
    main_topic_id: int
    top_topic_id: int
    is_default: bool = False
    message_links: list[str] = []


LANGUAGE_CHANNELS = [
    Channel(
        language="русский",
        utm_source="ruchat",
        channel_id=-1002181993369,
        main_topic_id=28,
        top_topic_id=29,
        is_default=True,
        message_links=[
            "https://t.me/airuforum/2",
            "https://t.me/airuforum/149",
            "https://t.me/airuforum/806",
            "https://t.me/airuforum/823",
            "https://t.me/airuforum/826"
        ]
    ),
    Channel(
        language="английский",
        utm_source="enchat",
        channel_id=-1002310317629,
        main_topic_id=20,
        top_topic_id=21,
        message_links=[
            "https://t.me/aienforum/2",
            "https://t.me/aienforum/115",
            "https://t.me/aienforum/1020",
            "https://t.me/aienforum/1029",
            "https://t.me/aienforum/1030"
        ]
    ),
    Channel(
        language="французский",
        utm_source="frchat",
        channel_id=-1002250186784,
        main_topic_id=2,
        top_topic_id=4,
        message_links=[
            "https://t.me/aifrforum/2",
            "https://t.me/aifrforum/100",
            "https://t.me/aifrforum/1009",
            "https://t.me/aifrforum/1019",
            "https://t.me/aifrforum/1020"
        ]
    ),
    Channel(
        language="хинди",
        language_note="Пиши латиницей.",
        utm_source="hichat",
        channel_id=-1002196847910,
        main_topic_id=2,
        top_topic_id=3,
        message_links=[
            "https://t.me/aihiforum/2",
            "https://t.me/aihiforum/49",
            "https://t.me/aihiforum/1006",
            "https://t.me/aihiforum/1013",
            "https://t.me/aihiforum/1014"
        ]
    )
]

LANGUAGE_CHANNELS_BY_ID = {channel.channel_id: channel for channel in LANGUAGE_CHANNELS}
