from django import forms
from .models import Proveedor

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'contacto', 'condicionesPago']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de la empresa o distribuidor'}),
            'contacto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Teléfono o Email'}),
            'condicionesPago': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ej. Pago a 30 días, efectivo...'}),
        }
