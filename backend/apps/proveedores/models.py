from django.db import models

class Proveedor(models.Model):
    nombre = models.CharField(max_length=200)
    contacto = models.CharField(max_length=200, blank=True, null=True)
    condicionesPago = models.TextField(blank=True, null=True, verbose_name="Condiciones de Pago")

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"

    def __str__(self):
        return self.nombre
