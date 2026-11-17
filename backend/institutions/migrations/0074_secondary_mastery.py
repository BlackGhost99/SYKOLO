import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def protect(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as c:
        c.execute("ALTER TABLE public.institutions_secondarymastery ENABLE ROW LEVEL SECURITY")
        c.execute("REVOKE ALL ON TABLE public.institutions_secondarymastery FROM PUBLIC")
        for role in ("anon","authenticated"):
            c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [role])
            if c.fetchone():
                c.execute(f'REVOKE ALL ON TABLE public.institutions_secondarymastery FROM "{role}"')


class Migration(migrations.Migration):
    dependencies = [("institutions","0073_course_unit_progress"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="SecondaryMastery", fields=[
            ("id",models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
            ("stage",models.CharField(max_length=16,choices=[("not_yet","À travailler"),("developing","En cours"),("achieved","Acquis")])),
            ("action",models.CharField(max_length=500,blank=True)),
            ("action_status",models.CharField(max_length=16,blank=True,choices=[("","Aucune action"),("planned","À engager"),("ongoing","En cours"),("completed","Réalisée")])),
            ("due_on",models.DateField(null=True,blank=True)),
            ("unit_title",models.CharField(max_length=180)),
            ("objectives_snapshot",models.TextField(max_length=2000,blank=True)),
            ("revision",models.PositiveIntegerField(default=1)),
            ("updated_at",models.DateTimeField(auto_now=True)),
            ("unit",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="institutions.courseunit")),
            ("enrollment",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,to="institutions.enrollment")),
            ("updated_by",models.ForeignKey(null=True,on_delete=django.db.models.deletion.SET_NULL,related_name="+",to=settings.AUTH_USER_MODEL)),
        ],options={"constraints":[
            models.UniqueConstraint(fields=["unit","enrollment"],name="yem_secondary_mastery_unique"),
            models.CheckConstraint(condition=models.Q(stage__in=["not_yet","developing","achieved"]),name="yem_secondary_stage_valid"),
            models.CheckConstraint(condition=models.Q(action_status__in=["planned","ongoing","completed"]) | models.Q(action_status="",action="",due_on__isnull=True),name="yem_secondary_action_valid"),
        ]}),
        migrations.RunPython(protect,migrations.RunPython.noop),
    ]
