from django.db import models
from django.contrib.auth import get_user_model


User = get_user_model()


class Asset(models.Model):
    """Asset model"""

    ASSET_TYPES = (
        ("stock", "Stock"),
        ("crypto", "Cryptocurrency"),
        ("etf", "ETF"),
        ("commodity", "Commodity"),
    )

    symbol = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPES)
    tag = models.CharField(max_length=255, null=True, blank=True)
    logo = models.URLField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["symbol", "name"],
                name="Symbol and name must be unique",
            )
        ]

    def __str__(self):
        return f"{self.symbol} - {self.name} - {self.asset_type}"


class Portfolio(models.Model):
    """Portfolio model"""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"Portfolio for {self.user} - {self.name}"

    def get_assets(self):
        # Retrieve the assets associated with this portfolio
        assets = Asset.objects.filter(transaction__portfolio=self).distinct()
        return assets


class Transaction(models.Model):
    """Transaction model"""

    TRANSACTION_TYPES = (
        ("buy", "Buy"),
        ("sell", "Sell"),
    )

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    price = models.FloatField()
    quantity = models.FloatField()
    fees = models.FloatField(blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.portfolio} - {self.asset} - {self.transaction_type} - {self.date}"
        )
