from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class SubjectStates(StatesGroup):
    waiting_name = State()
    waiting_exam_date = State()
    waiting_level = State()
    waiting_practical = State()
    waiting_lecture_subject = State()
    waiting_lecture_title = State()
    waiting_lecture_pages = State()


class FoodStates(StatesGroup):
    waiting_food = State()


class RoutineStates(StatesGroup):
    waiting_sleep = State()
    waiting_wake = State()
    waiting_days = State()


class SleepStates(StatesGroup):
    waiting_sleep_log = State()


class ReportStates(StatesGroup):
    waiting_delay_reason = State()


class AdminStates(StatesGroup):
    waiting_block_identifier = State()
    waiting_unblock_identifier = State()
    waiting_sub_identifier = State()
    waiting_sub_plan = State()
    waiting_sub_paid = State()
    waiting_revoke_identifier = State()


class FileStates(StatesGroup):
    waiting_pdf_subject = State()
