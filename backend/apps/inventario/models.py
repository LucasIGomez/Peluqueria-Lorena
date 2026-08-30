from django.db import models

class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stockActual = models.IntegerField(default=0, verbose_name="Stock Actual")
    stockMinimo = models.IntegerField(default=0, verbose_name="Stock Mínimo")
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"

    def descontarStock(self, cantidad):
        if self.stockActual >= cantidad:
            self.stockActual -= cantidad
            self.save()
            return True
        return False

    def verificarStockMinimo(self):
        return self.stockActual <= self.stockMinimo

    def __str__(self):
        return self.nombre
