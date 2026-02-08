import asyncio
import random
import re
from contextlib import suppress
from datetime import date
from enum import Enum

from aiogram import Router, Bot, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ForceReply, ReplyKeyboardRemove
from aiogram.utils.deep_linking import create_deep_link

import chatgpt
import config
import database
from callbacks import *
from config import *


class State(Enum):
    WAITING_FOR_POST = 1
    WAITING_FOR_WINS1 = 2
    WAITING_FOR_WINS2 = 3


bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
router = Router()

post_data = {}
wins_photo_ids = []

current_state = State.WAITING_FOR_POST
required_keys = ['chart_photo_id', 'stats_text', 'stats_file_id', 'win_photo_id']

state = config.load_state()


def get_text_length() -> int:
    today = date.today().isoformat()
    if state.last_600_usage_date == today:
        lengths, weights = zip(*((length, weight) for length, weight in TEXT_LENGTHS.items() if length != 600))
    else:
        lengths, weights = zip(*TEXT_LENGTHS.items())

    text_length = random.choices(lengths, weights)[0]
    if text_length == 600:
        state.last_600_usage_date = today
        config.save_state(state)

    return text_length


async def generate_post():
    if not all(key in post_data for key in required_keys):
        post_data.clear()
        return

    stats_message_id = None
    if state.moderation_enabled:
        stats_message = await bot.send_message(BOT_OWNER_ID, post_data['stats_text'])
        stats_message_id = stats_message.message_id

    post = database.save_post(database.Post(
        stats_text=post_data['stats_text'],
        generated_text=chatgpt.generate_text(post_data['stats_text'], get_text_length()),
        chart_photo_id=post_data['chart_photo_id'],
        stats_file_id=post_data['stats_file_id'],
        win_photo_id=post_data['win_photo_id'],
        stats_message_id=stats_message_id,
    ))
    post_data.clear()

    if state.moderation_enabled:
        await send_post_message(post)
    else:
        await publish_posts(post)


async def send_post_message(post: database.Post):
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=PUBLISH_POST_BUTTON, callback_data=PublishPost(post_id=post.id).pack())],
        [InlineKeyboardButton(text=EDIT_POST_BUTTON, callback_data=EditPost(post_id=post.id).pack())],
        [InlineKeyboardButton(text=DELETE_POST_BUTTON, callback_data=DeletePost(post_id=post.id).pack())]
    ])

    if post.text_voice_id:
        await bot.send_voice(BOT_OWNER_ID, post.text_voice_id, caption=post.generated_text, reply_markup=reply_markup, reply_to_message_id=post.stats_message_id)
    else:
        await bot.send_message(BOT_OWNER_ID, post.generated_text, reply_markup=reply_markup, reply_to_message_id=post.stats_message_id)


async def publish_posts(post: database.Post):
    chart_messages = {}

    for channel in LANGUAGE_CHANNELS:
        chart_messages[channel.channel_id] = await publish_post(post, channel)
        await asyncio.sleep(1)

    await asyncio.sleep(180)

    for channel in LANGUAGE_CHANNELS:
        await publish_post_win(post, channel, chart_messages[channel.channel_id])
        await asyncio.sleep(1)


async def publish_post(post: database.Post, channel: config.Channel):
    if channel.is_default:
        translated_text = post.generated_text
    else:
        translated_text = chatgpt.translate_text(channel.language, channel.language_note, post.generated_text)

    if not post.text_voice_id:
        chart_message = await bot.send_photo(channel.channel_id, post.chart_photo_id, caption=translated_text, reply_to_message_id=channel.main_topic_id)
    else:
        chart_message = await bot.send_photo(channel.channel_id, post.chart_photo_id, reply_to_message_id=channel.main_topic_id)
        await bot.send_voice(channel.channel_id, post.text_voice_id, caption=translated_text, reply_to_message_id=chart_message.message_id)

    await bot.send_document(channel.channel_id, post.stats_file_id, reply_to_message_id=channel.main_topic_id)

    post.is_published = True
    database.save_post(post)

    return chart_message


async def publish_post_win(post: database.Post, channel: config.Channel, chart_message):
    await bot.send_message(channel.channel_id, random.choice(WIN_EMOJIS), reply_to_message_id=channel.main_topic_id)
    win_message = await bot.send_photo(channel.channel_id, post.win_photo_id, reply_to_message_id=chart_message.message_id)

    database.save_win_message(
        database.WinMessage(
            channel_id=channel.channel_id,
            win_photo_id=post.win_photo_id,
            win_message_id=win_message.message_id,
            win_message_url=win_message.get_url(),
        )
    )


async def generate_wins_post():
    wins_post = database.save_wins_post(database.WinsPost(win_photo_ids=wins_photo_ids))
    wins_photo_ids.clear()

    if state.moderation_enabled:
        await send_wins_post_message(wins_post)
    else:
        await publish_wins_posts(wins_post)


async def send_wins_post_message(wins_post: database.WinsPost):
    reply_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=PUBLISH_POST_BUTTON, callback_data=PublishWinsPost(post_id=wins_post.id).pack())],
        [InlineKeyboardButton(text=DELETE_POST_BUTTON, callback_data=DeleteWinsPost(post_id=wins_post.id).pack())]
    ])

    total_photos = len(wins_post.win_photo_ids)
    for i in range(0, total_photos, 10):
        win_photos = [InputMediaPhoto(media=photo_id) for photo_id in wins_post.win_photo_ids[i:i + 10]]
        win_photos_messages = await bot.send_media_group(BOT_OWNER_ID, win_photos)

        if i + 10 >= total_photos:
            await win_photos_messages[-1].reply(WINS_POST_TEXT, reply_markup=reply_markup)


async def publish_wins_posts(wins_post: database.WinsPost):
    for channel in LANGUAGE_CHANNELS:
        await publish_wins_post(wins_post, channel)
        await asyncio.sleep(1)


async def publish_wins_post(wins_post: database.WinsPost, channel: config.Channel):
    for i in range(0, len(wins_post.win_photo_ids), 10):
        win_photos = [InputMediaPhoto(media=photo_id) for photo_id in wins_post.win_photo_ids[i:i + 10]]
        win_messages = await bot.send_media_group(channel.channel_id, win_photos, reply_to_message_id=channel.main_topic_id)

        for win_photo_id, win_message in zip(wins_post.win_photo_ids, win_messages):
            database.save_win_message(database.WinMessage(
                channel_id=channel.channel_id,
                win_photo_id=win_photo_id,
                win_message_id=win_message.message_id,
                win_message_url=win_message.get_url()
            ))

    wins_post.is_published = True
    database.save_wins_post(wins_post)


@router.channel_post(F.chat.id == WATCH_CHANNEL_ID)
async def handle_channel_post(message: Message):
    global current_state

    if message.text and '#stat' in message.text:
        post_data['stats_text'] = message.text.replace('#stat', '')

    if message.caption:
        if '#chart' in message.caption:
            post_data['chart_photo_id'] = message.photo[-1].file_id

        if '#file' in message.caption:
            post_data['stats_file_id'] = message.document.file_id

        if '#win' in message.caption:
            post_data['win_photo_id'] = message.photo[-1].file_id

            win_percent_match = re.search(r'(\d+(\.\d+)?)%', message.caption)
            win_percent = int(win_percent_match.group(1))

            database.save_win_percent(database.WinPercent(
                win_percent=win_percent,
                win_photo_id=message.photo[-1].file_id
            ))

            if current_state == State.WAITING_FOR_POST and state.generation_enabled:
                current_state = State.WAITING_FOR_WINS1
                await generate_post()

            elif win_percent >= WIN_BIG_PERCENT and state.generation_enabled:
                await generate_post()

            elif current_state in (State.WAITING_FOR_WINS1, State.WAITING_FOR_WINS2) or not state.generation_enabled:
                wins_photo_ids.append(message.photo[-1].file_id)

        if '#promo' in message.caption:
            for channel in LANGUAGE_CHANNELS:
                await message.copy_to(
                    channel.channel_id,
                    caption=message.caption.replace('#promo', ''),
                    reply_to_message_id=channel.main_topic_id
                )


@router.callback_query(PublishPost.filter())
async def publish_post_callback(callback: CallbackQuery, state: FSMContext, callback_data: PublishPost):
    post = database.get_post(callback_data.post_id)
    if not post or post.is_published:
        return

    await state.clear()
    await callback.answer()
    await callback.message.reply(POST_PUBLISHED_TEXT, reply_markup=ReplyKeyboardRemove())
    await publish_posts(post)


@router.callback_query(EditPost.filter())
async def edit_post_callback(callback: CallbackQuery, state: FSMContext, callback_data: EditPost):
    post = database.get_post(callback_data.post_id)
    if not post:
        return

    edit_message = await callback.message.reply(EDIT_POST_TEXT, reply_markup=ForceReply())
    await state.set_state(PostState.edit_post)
    await state.update_data(post_id=post.id, post_message_id=callback.message.message_id, edit_message_id=edit_message.message_id)
    await callback.answer()


@router.callback_query(DeletePost.filter())
async def delete_post_callback(callback: CallbackQuery, state: FSMContext, callback_data: DeletePost):
    post = database.get_post(callback_data.post_id)
    if post:
        database.delete_post(post)

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(POST_DELETED_TEXT, reply_markup=ReplyKeyboardRemove())
    await callback.answer()


@router.callback_query(PublishWinsPost.filter())
async def publish_wins_post_callback(callback: CallbackQuery, state: FSMContext, callback_data: PublishWinsPost):
    wins_post = database.get_wins_post(callback_data.post_id)
    if not wins_post or wins_post.is_published:
        return

    await state.clear()
    await callback.message.reply(POST_PUBLISHED_TEXT, reply_markup=ReplyKeyboardRemove())
    await callback.answer()
    await publish_wins_posts(wins_post)


@router.callback_query(DeleteWinsPost.filter())
async def delete_wins_post_callback(callback: CallbackQuery, state: FSMContext, callback_data: DeleteWinsPost):
    post = database.get_wins_post(callback_data.post_id)
    if post:
        database.delete_wins_post(post)

    await state.clear()
    await callback.message.delete()
    await callback.message.answer(POST_DELETED_TEXT)
    await callback.answer()


@router.message(PostState.edit_post)
async def edit_post_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    post = database.get_post(data['post_id'])

    with suppress(Exception):
        await message.delete()
        await bot.delete_message(message.chat.id, data['post_message_id'])
        await bot.delete_message(message.chat.id, data['edit_message_id'])

    if not post:
        await state.clear()
        return

    if message.voice:
        post.generated_text = message.html_text
        post.text_voice_id = message.voice.file_id
    elif message.html_text:
        post.generated_text = message.html_text
        post.text_voice_id = None
    else:
        await message.answer(INVALID_EDIT_TEXT, reply_markup=ForceReply())
        return

    database.save_post(post)

    await state.clear()
    await send_post_message(post)


@router.message(Command('admin'))
async def admin_command(message: Message):
    if message.from_user.id != BOT_OWNER_ID:
        return

    await message.answer(
        ADMIN_SETTINGS_TEXT,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MODERATION_BUTTON.format(status='✅' if state.moderation_enabled else '❌'), callback_data=ToggleModeration(enabled=state.moderation_enabled).pack())],
            [InlineKeyboardButton(text=GENERATION_BUTTON.format(status='✅' if state.generation_enabled else '❌'), callback_data=ToggleGeneration(enabled=state.generation_enabled).pack())]
        ])
    )


@router.callback_query(ToggleModeration.filter())
async def toggle_moderation_callback(callback: CallbackQuery, callback_data: ToggleModeration):
    state.moderation_enabled = not callback_data.enabled
    config.save_state(state)

    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MODERATION_BUTTON.format(status='✅' if state.moderation_enabled else '❌'), callback_data=ToggleModeration(enabled=state.moderation_enabled).pack())],
            [InlineKeyboardButton(text=GENERATION_BUTTON.format(status='✅' if state.generation_enabled else '❌'), callback_data=ToggleGeneration(enabled=state.generation_enabled).pack())]
        ])
    )


@router.callback_query(ToggleGeneration.filter())
async def toggle_requests_callback(callback: CallbackQuery, callback_data: ToggleGeneration):
    state.generation_enabled = not callback_data.enabled
    config.save_state(state)

    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=MODERATION_BUTTON.format(status='✅' if state.moderation_enabled else '❌'), callback_data=ToggleModeration(enabled=state.moderation_enabled).pack())],
            [InlineKeyboardButton(text=GENERATION_BUTTON.format(status='✅' if state.generation_enabled else '❌'), callback_data=ToggleGeneration(enabled=state.generation_enabled).pack())]
        ])
    )


@router.message(Command('button'))
async def button_command(message: Message, command: CommandObject):
    if message.from_user.id != BOT_OWNER_ID or not command.args:
        return

    args = command.args.split(maxsplit=2)
    message_url, button_url, button_text = (args + [None, None])[:3]

    match = re.match(r'https://t\.me/([^/]+)/(\d+)(?:/(\d+))?', message_url)
    if not match:
        await message.reply(INVALID_MESSAGE_URL_TEXT)
        return

    chat_id = match.group(1)
    message_id = int(match.group(3)) if match.group(3) else int(match.group(2))

    reply_markup = (
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=button_text, url=button_url)]])
        if button_url and button_text else None
    )

    try:
        await bot.edit_message_reply_markup(
            chat_id=f'@{chat_id}' if not chat_id.isdigit() else chat_id,
            message_id=message_id,
            reply_markup=reply_markup
        )

        await message.reply(BUTTON_EDITED_TEXT if reply_markup else BUTTON_DELETED_TEXT)
    except TelegramBadRequest as error:
        await message.reply(BUTTON_NOT_EDITED_TEXT.format(error=error.message))


async def update_state():
    global current_state

    if current_state == State.WAITING_FOR_WINS1:
        current_state = State.WAITING_FOR_WINS2
    elif current_state == State.WAITING_FOR_WINS2:
        current_state = State.WAITING_FOR_POST
        if wins_photo_ids:
            await generate_wins_post()


async def send_best_win_percent():
    best_win_percent = database.get_best_win_percent()
    if not best_win_percent:
        return

    best_win_messages = database.get_win_messages(best_win_percent.win_photo_id)
    if not best_win_messages:
        return

    for win_message in best_win_messages:
        channel = LANGUAGE_CHANNELS_BY_ID.get(win_message.channel_id)
        if not channel:
            continue

        best_win_caption = (
            f'👉 <a href="{win_message.win_message_url}?thread={channel.main_topic_id}">'
            f'{win_message.created_at.strftime("%Y/%m/%d %H:%M")}</a>'
        )

        await bot.copy_message(
            win_message.channel_id, win_message.channel_id, win_message.win_message_id,
            caption=best_win_caption, reply_to_message_id=channel.top_topic_id
        )


async def send_message_links():
    for channel in LANGUAGE_CHANNELS:
        if not channel.message_links:
            continue

        current_index = state.current_link_index.get(channel.channel_id, 0)
        link_to_send = channel.message_links[current_index]

        state.current_link_index[channel.channel_id] = (current_index + 1) % len(channel.message_links)
        config.save_state(state)

        await bot.send_message(
            channel.channel_id,
            link_to_send,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🧠 AI Signal Bot', url=create_deep_link('signalsearchrobot', 'start', channel.utm_source))]
            ]),
            reply_to_message_id=channel.top_topic_id
        )
