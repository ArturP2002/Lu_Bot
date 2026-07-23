"""FSM-состояния."""

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    language = State()
    rules = State()
    name = State()
    photo = State()
    gender = State()
    seeking = State()
    visible_to = State()
    contact = State()
    age = State()
    bio = State()
    city = State()
    goal_title = State()
    goal_amount = State()
    preview = State()


class ProfileEdit(StatesGroup):
    age = State()
    gender = State()
    seeking = State()
    visible_to = State()
    photo = State()
    city = State()
    bio = State()
    language = State()


class SparksFlow(StatesGroup):
    amount = State()
    method = State()
    requisites = State()


class RatingFlow(StatesGroup):
    comment = State()
    support_amount = State()
    report = State()


class GoalFlow(StatesGroup):
    title = State()
    amount = State()


class EventCreate(StatesGroup):
    title = State()
    city = State()
    address = State()
    datetime = State()
    price = State()
    men = State()
    women = State()
    category = State()
    photo = State()
    description = State()


class EventEdit(StatesGroup):
    waiting = State()


class EventReport(StatesGroup):
    text = State()


class VerificationFlow(StatesGroup):
    video = State()


class LumaChat(StatesGroup):
    waiting = State()
