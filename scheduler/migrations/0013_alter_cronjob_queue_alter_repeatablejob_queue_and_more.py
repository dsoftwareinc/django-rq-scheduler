# Generated by Django 4.2.1 on 2023-05-11 16:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scheduler", "0012_alter_cronjob_name_alter_repeatablejob_name_and_more")
    ]

    operations = [
        migrations.AlterField(
            model_name="cronjob",
            name="queue",
            field=models.CharField(
                choices=[("default", "default"), ("low", "low"), ("high", "high")],
                help_text="Queue name",
                max_length=255,
                verbose_name="queue",
            ),
        ),
        migrations.AlterField(
            model_name="repeatablejob",
            name="queue",
            field=models.CharField(
                choices=[("default", "default"), ("low", "low"), ("high", "high")],
                help_text="Queue name",
                max_length=255,
                verbose_name="queue",
            ),
        ),
        migrations.AlterField(
            model_name="scheduledjob",
            name="queue",
            field=models.CharField(
                choices=[("default", "default"), ("low", "low"), ("high", "high")],
                help_text="Queue name",
                max_length=255,
                verbose_name="queue",
            ),
        ),
    ]