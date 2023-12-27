from django.contrib import admin

from octofolio import models

admin.site.register(models.Asset)
admin.site.register(models.Portfolio)


class TransactionModelAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "asset":
            kwargs["queryset"] = models.Asset.objects.order_by("symbol")
        return super(TransactionModelAdmin, self).formfield_for_foreignkey(
            db_field, request, **kwargs
        )


admin.site.register(models.Transaction, TransactionModelAdmin)
