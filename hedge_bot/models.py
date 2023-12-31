from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from django.core.exceptions import ValidationError


User = get_user_model()


class Exchange(models.Model):
    """Exchange model"""

    name = models.CharField(max_length=255, unique=True)
    exchange_id = models.CharField(max_length=255, unique=True)
    spot_fee = models.FloatField(default=0.001)
    future_fee = models.FloatField(default=0.0005)
    spot = models.BooleanField(default=True)
    future = models.BooleanField(default=True)
    logo = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"{self.name}- Spot: {self.spot} - Future: {self.future}"


class ExchangeApi(models.Model):
    """Exchange API tokens"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    exchange = models.ForeignKey(Exchange, on_delete=models.CASCADE)
    public_key = models.CharField(max_length=255)
    private_key = models.CharField(max_length=255)
    group = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "exchange"],
                name="Same user cannot have api for the same exchange",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.exchange}"


class HedgeBot(models.Model):
    """HedgeBot model"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tick = models.CharField(max_length=255)
    exchanges = models.JSONField()
    settings = models.JSONField()
    status = models.BooleanField(default=False)
    max_size = models.IntegerField(default=1000)
    control_size = models.IntegerField(default=50)
    tx_size = models.IntegerField(default=40)
    min_open_profit = models.FloatField(default=0.01)
    min_close_profit = models.FloatField(default=0.005)
    created_at = models.DateTimeField(default=now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tick"],
                condition=models.Q(status=True),
                name="unique_active_tick_per_user",
            )
        ]

    def clean(self):
        super().clean()
        if (
            self.status == "1"
            and HedgeBot.objects.exclude(pk=self.pk)
            .filter(user=self.user, tick=self.tick, status=True)
            .exists()
        ):
            raise ValidationError("You already have an active bot with this tick.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user} - {self.tick} - {self.status}"


class HedgeBotTx(models.Model):
    """HedgeBot transaction model"""

    SIDE_CHOICES = (
        ("open", "Open"),
        ("close", "Close"),
    )

    bot = models.ForeignKey(HedgeBot, on_delete=models.CASCADE)
    side = models.CharField(max_length=255, choices=SIDE_CHOICES)
    spot_cost_price = models.FloatField()
    hedge_cost_price = models.FloatField()
    spot_price = models.FloatField(blank=True, null=True)
    hedge_price = models.FloatField(blank=True, null=True)
    spot_exchange = models.ForeignKey(
        Exchange, on_delete=models.CASCADE, related_name="spot_exchange"
    )
    hedge_exchange = models.ForeignKey(
        Exchange, on_delete=models.CASCADE, related_name="hedge_exchange"
    )
    spot_quantity = models.FloatField()
    hedge_quantity = models.FloatField()
    fee = models.FloatField()
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.bot} - {self.side} - {self.created_at}"


class HedgeBotBlacklist(models.Model):
    """HedgeBot blacklist model"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tick = models.CharField(max_length=255)
    spot_exchange = models.ForeignKey(
        Exchange, on_delete=models.CASCADE, related_name="blacklist_spot_exchange"
    )
    hedge_exchange = models.ForeignKey(
        Exchange, on_delete=models.CASCADE, related_name="blacklist_hedge_exchange"
    )
    until_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.tick} - {self.spot_exchange.name} - {self.hedge_exchange.name}"
