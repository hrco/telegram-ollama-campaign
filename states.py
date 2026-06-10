from aiogram.fsm.state import State, StatesGroup

class CampaignCreation(StatesGroup):
    waiting_for_topic = State()
    waiting_for_confirmation = State()