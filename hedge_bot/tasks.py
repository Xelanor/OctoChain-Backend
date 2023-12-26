from octochain.celery import app

from hedge_bot.bot.hedge_bot import HedgeBotClass


@app.task
def run_hedge_bot():
    bot = HedgeBotClass(1)
