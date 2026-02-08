from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import StatesGroup, State


class PostState(StatesGroup):
    edit_post = State()


class PublishPost(CallbackData, prefix='pp'):
    post_id: int


class EditPost(CallbackData, prefix='ep'):
    post_id: int


class DeletePost(CallbackData, prefix='dp'):
    post_id: int


class PublishWinsPost(CallbackData, prefix='pwp'):
    post_id: int


class DeleteWinsPost(CallbackData, prefix='dwp'):
    post_id: int


class ToggleModeration(CallbackData, prefix='tm'):
    enabled: bool


class ToggleGeneration(CallbackData, prefix='tr'):
    enabled: bool
