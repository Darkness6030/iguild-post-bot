import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Iterable

from sqlmodel import SQLModel, Field, create_engine, Session, select


class BaseModel(SQLModel):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Post(BaseModel, table=True):
    stats_text: str
    generated_text: str
    chart_photo_id: str
    stats_file_id: str
    win_photo_id: str
    text_voice_id: Optional[str] = None
    stats_message_id: Optional[int] = None
    is_published: bool = False


class WinsPost(BaseModel, table=True):
    win_photo_ids_json: str = Field(repr=False, nullable=False)
    is_published: bool = False

    @property
    def win_photo_ids(self) -> list[str]:
        return json.loads(self.win_photo_ids_json)

    @win_photo_ids.setter
    def win_photo_ids(self, value: list[str]):
        self.win_photo_ids_json = json.dumps(value)

    def __init__(self, win_photo_ids: list[str], **kwargs):
        super().__init__(**kwargs)
        self.win_photo_ids = win_photo_ids


class WinPercent(BaseModel, table=True):
    win_photo_id: str
    win_percent: int


class WinMessage(BaseModel, table=True):
    channel_id: int
    win_photo_id: str
    win_message_id: int
    win_message_url: str


engine = create_engine("sqlite:///database.db")
session = Session(engine)

SQLModel.metadata.create_all(engine)


def save_post(post: Post) -> Post:
    session.add(post)
    session.commit()
    return post


def get_post(post_id: int) -> Optional[Post]:
    return session.get(Post, post_id)


def delete_post(post: Post):
    session.delete(post)
    session.commit()


def save_wins_post(wins_post: WinsPost) -> WinsPost:
    session.add(wins_post)
    session.commit()
    return wins_post


def get_wins_post(post_id: int) -> Optional[WinsPost]:
    return session.get(WinsPost, post_id)


def delete_wins_post(wins_post: WinsPost):
    session.delete(wins_post)
    session.commit()


def save_win_percent(win_percent: WinPercent) -> WinPercent:
    session.add(win_percent)
    session.commit()
    return win_percent


def get_best_win_percent() -> Optional[WinPercent]:
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    query = (
        select(WinPercent)
        .join(WinMessage, WinPercent.win_photo_id == WinMessage.win_photo_id)  # type: ignore
        .where(WinPercent.created_at >= yesterday)
        .order_by(WinPercent.win_percent.desc())
    )

    return session.exec(query).first()


def save_win_message(win_message: WinMessage) -> WinMessage:
    session.add(win_message)
    session.commit()
    return win_message


def get_win_messages(win_photo_id: str) -> Iterable[WinMessage]:
    query = select(WinMessage).where(WinMessage.win_photo_id == win_photo_id)
    return session.exec(query).all()
