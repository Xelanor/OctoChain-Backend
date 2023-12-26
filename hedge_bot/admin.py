from django.contrib import admin

from hedge_bot import models

admin.site.register(models.Exchange)
admin.site.register(models.ExchangeApi)
admin.site.register(models.HedgeBot)
admin.site.register(models.HedgeBotTx)
