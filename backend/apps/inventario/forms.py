from django import forms
from .models import Producto

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'precio', 'stockActual', 'stockMinimo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stockActual': forms.NumberInput(attrs={'class': 'form-control'}),
            'stockMinimo': forms.NumberInput(attrs={'class': 'form-control'}),
        }
