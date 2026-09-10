"""
Peluquería Lorena — Comando para generar productos de prueba en el catálogo de inventario.

Uso:
    python manage.py generar_productos
    python manage.py generar_productos --cantidad 50
    python manage.py generar_productos --cantidad 20 --limpiar
"""
import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import models, transaction
from django.utils import timezone

from apps.inventario.models import MovimientoStock, Producto


CATALOGO_BASE = [
    # Tinturas y Coloración (UNIDAD)
    {"nombre": "Tintura Schwarzkopf Igora Royal 7-1 Rubio Ceniza", "unidad": "UNIDAD", "precio": 9200, "desc": "Coloración permanente profesional de máxima cobertura de canas."},
    {"nombre": "Tintura L'Oréal Majirel 5.0 Castaño Claro", "unidad": "UNIDAD", "precio": 9800, "desc": "Coloración crema de belleza con Ioneno G e Incell."},
    {"nombre": "Tintura L'Oréal Dialight 9.12 Milkshake Nacarado", "unidad": "UNIDAD", "precio": 10500, "desc": "Tono sobre tono ácido sin amoníaco para matizar decoloraciones."},
    {"nombre": "Tintura Silkey Policrom 6.34 Rubio Oscuro Dorado Cobrizo", "unidad": "UNIDAD", "precio": 6400, "desc": "Coloración crema con micropigmentos y keratina vegetal."},
    {"nombre": "Tintura Wella Koleston Perfect 8.0 Rubio Claro Puro", "unidad": "UNIDAD", "precio": 9600, "desc": "Tecnología ME+ para reducir el riesgo de alergias."},
    {"nombre": "Tintura Fantasía Otowil Violeta Eléctrico 50g", "unidad": "UNIDAD", "precio": 3200, "desc": "Coloración semipermanente directa sin amoníaco."},
    {"nombre": "Tonalizador Salerm Gray Clay Ceniza Plata", "unidad": "UNIDAD", "precio": 7800, "desc": "Crema matizadora para rubios fríos y neutralización de amarillos."},
    {"nombre": "Tintura Schwarzkopf Igora Royal 9-7 Rubio Muy Claro Cobrizo", "unidad": "UNIDAD", "precio": 9200, "desc": "Tono cobrizo vibrante de alta fijación."},
    {"nombre": "Tintura L'Oréal Majirel 1.0 Negro Profundo", "unidad": "UNIDAD", "precio": 9800, "desc": "Negro clásico brillante con tecnología protectora."},
    {"nombre": "Tintura Alfaparf Evolution of the Color 8.21", "unidad": "UNIDAD", "precio": 8900, "desc": "Fórmula con ácido hialurónico y cristales de color."},

    # Oxidantes y Reveladores (LITRO y ML)
    {"nombre": "Oxidante en Crema 20 Vol. Schwarzkopf 1000ml", "unidad": "LITRO", "precio": 12500, "desc": "Agua oxigenada estabilizada 6% para tinturas y decoloraciones."},
    {"nombre": "Oxidante en Crema 30 Vol. L'Oréal Blond Studio 1000ml", "unidad": "LITRO", "precio": 14200, "desc": "Activador de 9% con agentes suavizantes y lípidos."},
    {"nombre": "Oxidante en Crema 40 Vol. Silkey Dylex 1000ml", "unidad": "LITRO", "precio": 9800, "desc": "Agua oxigenada de 12% para aclaraciones intensas."},
    {"nombre": "Revelador Dialight 6 Vol. L'Oréal 1000ml", "unidad": "LITRO", "precio": 13800, "desc": "Activador suave específico para baños de luz y matizadores."},
    {"nombre": "Activador Tono sobre Tono 10 Vol. Bonmetique 900ml", "unidad": "ML", "precio": 8200, "desc": "Emulsión oxidante suave 3% para depósito de color."},

    # Decolorantes (KG y G)
    {"nombre": "Polvo Decolorante Schwarzkopf Blondme 9+ Tonos 450g", "unidad": "G", "precio": 28500, "desc": "Polvo aclarante con tecnología bonding anti-rotura integrada."},
    {"nombre": "Decolorante Azul Bonmetique Ultra Aclarado 500g", "unidad": "G", "precio": 14900, "desc": "Microgránulos azules antiamarillos de rápida acción."},
    {"nombre": "Pasta Decolorante L'Oréal Platinium Plus 500g", "unidad": "G", "precio": 36000, "desc": "Pasta aclarante con cera blanca de abejas y nutrición."},
    {"nombre": "Polvo Decolorante Blanco Salerm Sin Amoníaco 500g", "unidad": "G", "precio": 18200, "desc": "Fórmula hipoalergénica respetuosa del cuero cabelludo."},
    {"nombre": "Polvo Decolorante Profesional Bidón 1kg Blond Max", "unidad": "KG", "precio": 31000, "desc": "Envase económico de 1 kilo para trabajos de salón."},

    # Shampoos Técnicos (LITRO y ML)
    {"nombre": "Shampoo Neutro Bidón 5L Limpieza Profunda", "unidad": "LITRO", "precio": 18500, "desc": "Bidón técnico pH 7 para lavado previo a tratamientos químicos."},
    {"nombre": "Shampoo Matizador Violeta Silver L'Oréal 1500ml", "unidad": "LITRO", "precio": 32000, "desc": "Con pigmentos violetas para neutralizar reflejos cobrizos/amarillos."},
    {"nombre": "Shampoo Ácido Post-Color Biferdil 1000ml", "unidad": "LITRO", "precio": 14500, "desc": "Fórmula ácida pH 4.5 para cerrar la cutícula tras teñir."},
    {"nombre": "Shampoo Antirresiduos Pre-Alisado Keratimax 1L", "unidad": "LITRO", "precio": 11900, "desc": "Dilatador de cutícula previo a shock de keratina o alisado."},
    {"nombre": "Shampoo Loreal Absolut Repair Gold Quinoa 1500ml", "unidad": "LITRO", "precio": 34500, "desc": "Reparación profunda instantánea para cabellos dañados."},
    {"nombre": "Shampoo Nutritivo de Argán y Macadamia 1000ml", "unidad": "LITRO", "precio": 13200, "desc": "Limpieza suave hidratante de uso diario en pileta."},
    {"nombre": "Shampoo Desenredante Manzanilla y Miel 1000ml", "unidad": "ML", "precio": 9500, "desc": "Ideal para cabellos finos y tonos claros."},

    # Acondicionadores y Máscaras (LITRO, KG, G, UNIDAD)
    {"nombre": "Acondicionador Desenredante Ácido Bidón 5L", "unidad": "LITRO", "precio": 19800, "desc": "Sellador cuticular para pileta con aroma frutal."},
    {"nombre": "Máscara Reparadora L'Oréal Absolut Repair 500g", "unidad": "G", "precio": 27900, "desc": "Tratamiento de nutrición lipídica profunda con enjuague."},
    {"nombre": "Tratamiento Intensivo Olaplex N°3 Hair Perfector 100ml", "unidad": "ML", "precio": 42000, "desc": "Reconstructor molecular de puentes de disulfuro."},
    {"nombre": "Baño de Crema Nutrición Intensa Palta y Karité 1kg", "unidad": "KG", "precio": 16500, "desc": "Máscara hiper-nutritiva en pote de 1 kilogramo."},
    {"nombre": "Máscara Blondme Keratin Restore Rubios Fríos 500ml", "unidad": "ML", "precio": 25400, "desc": "Reparación con pigmentos fríos para mantener el platino."},
    {"nombre": "Ampollas Cauterización Molecular Biferdil Caja x12u", "unidad": "UNIDAD", "precio": 15800, "desc": "Dosis individuales concentradas de keratina hidrolizada."},
    {"nombre": "Ampollas Semillas de Lino Brillo Instantáneo x10u", "unidad": "UNIDAD", "precio": 11200, "desc": "Tratamiento de shock nutritivo iluminador."},
    {"nombre": "Crema de Enjuague Nutritiva Aloe Vera 1000ml", "unidad": "LITRO", "precio": 8900, "desc": "Desenredante ligero para cabellos normales a secos."},

    # Alisados, Botox y Tratamientos Térmicos (LITRO, KG, ML)
    {"nombre": "Alisado Progresivo Libre de Formol Termoactivo 1L", "unidad": "LITRO", "precio": 29000, "desc": "Tratamiento alisador a base de ácido hialurónico y carbocisteína."},
    {"nombre": "Botox Capilar Rellenador Molecular en Pote 1kg", "unidad": "KG", "precio": 24500, "desc": "Rellena fibra capilar eliminando encrespamiento y frizz."},
    {"nombre": "Shock de Keratina Hidrolizada en Loción 500ml", "unidad": "ML", "precio": 13900, "desc": "Aporte de proteína para cabellos porosos post-decoloración."},
    {"nombre": "Sellador Cuticular Ácido Post-Química 500ml", "unidad": "ML", "precio": 11500, "desc": "Spray estabilizador de pH y brillo efecto espejo."},
    {"nombre": "Cauterizador Térmico de Puntas Abiertas 250ml", "unidad": "ML", "precio": 9900, "desc": "Tratamiento termoprotector sellador de puntas abiertas."},

    # Peinado, Fijación y Finalizadores (ML, G, UNIDAD)
    {"nombre": "Laca Fijación Extra Fuerte Schwarzkopf Silhouette 500ml", "unidad": "ML", "precio": 18200, "desc": "Fijación invisible de larga duración sin dejar residuos."},
    {"nombre": "Protector Térmico Bifásico Anti-Frizz Silkey 200ml", "unidad": "ML", "precio": 8400, "desc": "Protege del calor de planchita y buclera hasta 230°C."},
    {"nombre": "Sérum Óleo Extraordinario L'Oréal Mythic Oil 100ml", "unidad": "ML", "precio": 26000, "desc": "Aceite de argán y palta para acabado suave y sedoso."},
    {"nombre": "Cera Mate Modeladora Osis+ Mess Up 100g", "unidad": "G", "precio": 15600, "desc": "Efecto mate texturizado para peinados cortos y cortes unisex."},
    {"nombre": "Mousse Modelador Volumen y Rizos Moroccanoil 300ml", "unidad": "ML", "precio": 24800, "desc": "Espuma liviana para rulos sin sensación pegajosa."},
    {"nombre": "Brillo en Spray Efecto Espejo Alfaparf 200ml", "unidad": "ML", "precio": 12800, "desc": "Toque final luminoso con semillas de lino."},
    {"nombre": "Gel Fijador Ultra Fuerte Efecto Húmedo 500g", "unidad": "G", "precio": 6500, "desc": "Fijación extrema de larga duración sin descamación."},

    # Insumos y Descartables de Salón (UNIDAD)
    {"nombre": "Capas Descartables Transparentes Tintura Pack x50u", "unidad": "UNIDAD", "precio": 8500, "desc": "Polietileno impermeable de 120x80cm."},
    {"nombre": "Guantes de Nitrilo Negros Talle M Caja x100u", "unidad": "UNIDAD", "precio": 14500, "desc": "Resistentes a decolorantes y tinturas, sin talco."},
    {"nombre": "Papel Térmico para Mechas y Balayage Caja x250u", "unidad": "UNIDAD", "precio": 16900, "desc": "Láminas térmicas lavables y reutilizables."},
    {"nombre": "Broches Separadores Tipo Cocodrilo Pack x12u", "unidad": "UNIDAD", "precio": 5200, "desc": "Agarre firme para seccionar cabello grueso o fino."},
    {"nombre": "Gorros Térmicos Metalizados para Reflejos Pack x10u", "unidad": "UNIDAD", "precio": 4800, "desc": "Potencia la penetración de baños de crema y máscaras."},
    {"nombre": "Pinceles Anchos para Tintura Cerdas Suaves Pack x6u", "unidad": "UNIDAD", "precio": 6100, "desc": "Cerdas en ángulo para precisión en raíces y balayage."},
    {"nombre": "Bolls Graduados de Plástico para Tintura x4u", "unidad": "UNIDAD", "precio": 5800, "desc": "Con base antideslizante y marcas de mililitros."},
    {"nombre": "Toallas de Microfibra Negras Superabsorbentes x10u", "unidad": "UNIDAD", "precio": 22000, "desc": "Secado rápido y resistencia a manchas de decoloración."}
]


class Command(BaseCommand):
    help = "Genera un conjunto de productos de prueba realistas para Peluquería Lorena en la base de datos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cantidad",
            type=int,
            default=50,
            help="Número de productos a generar (por defecto 50).",
        )
        parser.add_argument(
            "--limpiar",
            action="store_true",
            help="Si se indica, elimina los productos existentes antes de generar los nuevos.",
        )

    def handle(self, *args, **options):
        cantidad = options["cantidad"]
        if cantidad <= 0:
            self.stdout.write(self.style.ERROR("La cantidad debe ser mayor a 0."))
            return

        if options["limpiar"]:
            self.stdout.write(self.style.WARNING("Limpiando inventario antes de generar..."))
            with transaction.atomic():
                MovimientoStock.objects.all().delete()
                Producto.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("✔ Inventario anterior limpiado."))

        self.stdout.write(self.style.NOTICE(f"Generando {cantidad} productos en la base de datos..."))

        creados = 0
        total_catalogo = len(CATALOGO_BASE)

        with transaction.atomic():
            for i in range(cantidad):
                base = CATALOGO_BASE[i % total_catalogo]
                ciclo = i // total_catalogo

                nombre = base["nombre"]
                if ciclo > 0:
                    nombre = f"{nombre} (Lote #{ciclo + 1})"

                unidad = base["unidad"]
                precio = Decimal(str(base["precio"]))

                # Variar stock y alertas de manera realista:
                # ~70% con stock normal saludable
                # ~20% con stock crítico (bajo stock_minimo)
                # ~10% con stock agotado (0)
                r = random.random()
                if unidad == "UNIDAD":
                    stock_min = random.choice([3, 5, 8, 10])
                    if r < 0.10:
                        stock_act = 0
                    elif r < 0.30:
                        stock_act = random.randint(1, stock_min)
                    else:
                        stock_act = random.randint(stock_min + 2, stock_min + 30)
                elif unidad in ["LITRO", "KG"]:
                    stock_min = random.choice([2, 3, 5])
                    if r < 0.10:
                        stock_act = 0
                    elif r < 0.30:
                        stock_act = random.randint(1, stock_min)
                    else:
                        stock_act = random.randint(stock_min + 1, stock_min + 15)
                else:  # ML, G
                    stock_min = random.choice([100, 200, 500])
                    if r < 0.10:
                        stock_act = 0
                    elif r < 0.30:
                        stock_act = random.randint(50, stock_min)
                    else:
                        stock_act = random.randint(stock_min + 100, stock_min + 2500)

                producto = Producto.objects.create(
                    nombre=nombre,
                    descripcion=base.get("desc", ""),
                    precio=precio,
                    stock_actual=stock_act,
                    stock_minimo=stock_min,
                    unidad_medida=unidad,
                    activo=True,
                    creado_en=timezone.now(),
                )

                # Registrar movimiento de alta de auditoría
                MovimientoStock.objects.create(
                    producto=producto,
                    tipo_movimiento=MovimientoStock.TipoMovimiento.ALTA_PRODUCTO,
                    cantidad=stock_act,
                    stock_previo=0,
                    stock_posterior=stock_act,
                    motivo=f"Alta inicial en catálogo ({stock_act} {producto.unidad_abreviatura}).",
                    fecha=timezone.now(),
                )
                creados += 1

        total_actual = Producto.objects.count()
        bajo_stock = Producto.objects.filter(stock_actual__lte=models.F("stock_minimo")).count() if hasattr(models, 'F') else 0

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✔ ¡Generación completada exitosamente!\n"
                f"  - Productos creados: {creados}\n"
                f"  - Total de productos en base de datos: {total_actual}\n"
                f"Todos los productos incluyen unidades de medida, precios, stock y trazabilidad de movimientos."
            )
        )
