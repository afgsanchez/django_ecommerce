# Generated by Django 5.2.1 on 2025-06-23 15:14

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0016_promocion'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['name'], 'verbose_name': 'Producto', 'verbose_name_plural': 'Productos'},
        ),
        migrations.AddField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True, help_text='Descripción corta del producto.', null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='long_description',
            field=models.TextField(blank=True, help_text='Descripción detallada y características del producto.', null=True),
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='product_additional_images/')),
                ('alt_text', models.CharField(blank=True, help_text='Texto alternativo para la imagen (SEO y accesibilidad)', max_length=255)),
                ('order', models.IntegerField(default=0, help_text='Orden de visualización de la imagen')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='additional_images', to='store.product')),
            ],
            options={
                'verbose_name': 'Imagen de Producto Adicional',
                'verbose_name_plural': 'Imágenes de Productos Adicionales',
                'ordering': ['order'],
            },
        ),
    ]
