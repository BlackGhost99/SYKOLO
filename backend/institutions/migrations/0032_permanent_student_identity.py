import uuid

from django.db import migrations, models
from django.db.models import deletion


def backfill_identities(apps, schema_editor):
    Student = apps.get_model("institutions", "Student")
    Identity = apps.get_model("institutions", "StudentIdentity")
    database = schema_editor.connection.alias
    while True:
        batch = list(Student.objects.using(database).filter(identity_id=None).order_by("pk")[:1000])
        if not batch:
            break
        Identity.objects.using(database).bulk_create([Identity(id=student.pk) for student in batch])
        for student in batch:
            student.identity_id = student.pk
        Student.objects.using(database).bulk_update(batch, ["identity"])
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def protect_identity_table(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute('ALTER TABLE "institutions_studentidentity" ENABLE ROW LEVEL SECURITY')


class Migration(migrations.Migration):
    dependencies = [("institutions", "0031_schoolmember_cycle_scope")]
    operations = [
        migrations.CreateModel(
            name="StudentIdentity",
            fields=[("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False))],
        ),
        migrations.RunPython(protect_identity_table, migrations.RunPython.noop),
        migrations.AddField(
            model_name="student", name="identity",
            field=models.ForeignKey(blank=True, editable=False, null=True, on_delete=deletion.PROTECT,
                                    to="institutions.studentidentity"),
        ),
        migrations.RunPython(backfill_identities, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="student", name="identity",
            field=models.ForeignKey(blank=True, editable=False, on_delete=deletion.PROTECT,
                                    to="institutions.studentidentity"),
        ),
        migrations.AlterField(model_name="student", name="student_code", field=models.SlugField(blank=True, max_length=50)),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(fields=("school", "identity"), name="unique_school_student_identity"),
        ),
    ]
