from octochain.celery import app

from hedge_bot.bot.hedge_bot import HedgeBotClass
from hedge_bot.bot.hedge_bot_open import HedgeBotOpenClass


@app.task
def run_hedge_bot(bot_id):
    bot = HedgeBotClass(bot_id)
    bot.run()


@app.task
def run_hedge_open_bot():
    bot = HedgeBotOpenClass()
    bot.run()
