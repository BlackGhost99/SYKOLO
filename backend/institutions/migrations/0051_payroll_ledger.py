"""M3.3: confidential payroll ledger with restricted PostgreSQL tables."""
import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def restrict_tables(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        for table in ("institutions_staffpayrun", "institutions_staffpaydisbursement"):
            cursor.execute(f'ALTER TABLE "public"."{table}" ENABLE ROW LEVEL SECURITY')
            cursor.execute("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
            for (role,) in cursor.fetchall():
                cursor.execute(f'REVOKE ALL PRIVILEGES ON TABLE "public"."{table}" FROM "{role}"')


def grant_standard_roles(apps, schema_editor):
    Role=apps.get_model("institutions", "SchoolRole")
    alias=schema_editor.connection.alias
    for role in Role.objects.using(alias).filter(code__in=("direction","comptabilite","econome")).iterator():
        existing=set(role.permissions or [])
        grants=set()
        if role.code=="direction" and {"school.staff.read","school.finance.approve"}<=existing:
            grants={"school.payroll.read","school.payroll.approve"}
        elif role.code=="comptabilite" and {"school.finance.read","school.finance.approve"}<=existing:
            grants={"school.payroll.read","school.payroll.manage","school.payroll.reverse"}
        elif role.code=="econome" and {"school.finance.read","school.finance.receive"}<=existing:
            grants={"school.payroll.read","school.payroll.pay"}
        if grants-existing:
            role.permissions=sorted(existing|grants)
            role.revision+=1
            role.save(update_fields=("permissions","revision"))


class Migration(migrations.Migration):
    dependencies=[
        ("institutions","0050_staff_professional_dossier"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations=[
        migrations.CreateModel(
            name="StaffPayRun",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
                ("period",models.DateField()),
                ("basis",models.CharField(max_length=20,default="monthly")),
                ("gross_amount",models.DecimalField(max_digits=12,decimal_places=2)),
                ("deductions",models.DecimalField(max_digits=12,decimal_places=2,default=0)),
                ("currency",models.CharField(max_length=3,default="XAF")),
                ("note",models.CharField(max_length=240,blank=True)),
                ("revision",models.PositiveIntegerField(default=1)),
                ("approved_at",models.DateTimeField(blank=True,null=True)),
                ("created_at",models.DateTimeField(auto_now_add=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_payruns",to="institutions.school")),
                ("staff",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="payruns",to="institutions.staffrecord")),
                ("year",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_payruns",to="institutions.academicyear")),
                ("prepared_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="prepared_staff_payruns",to=settings.AUTH_USER_MODEL)),
                ("approved_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="approved_staff_payruns",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="StaffPayDisbursement",
            fields=[
                ("id",models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,serialize=False)),
                ("amount",models.DecimalField(max_digits=12,decimal_places=2)),
                ("method",models.CharField(max_length=20)),
                ("reference",models.CharField(max_length=120)),
                ("paid_on",models.DateField()),
                ("idempotency_key",models.UUIDField()),
                ("recorded_at",models.DateTimeField(auto_now_add=True)),
                ("voided_at",models.DateTimeField(blank=True,null=True)),
                ("void_reason",models.CharField(max_length=240,blank=True)),
                ("school",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="staff_disbursements",to="institutions.school")),
                ("pay_run",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="disbursements",to="institutions.staffpayrun")),
                ("recorded_by",models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,related_name="recorded_staff_disbursements",to=settings.AUTH_USER_MODEL)),
                ("voided_by",models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="voided_staff_disbursements",to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="staffpayrun",
            constraint=models.UniqueConstraint(fields=("school","staff","period","basis"),name="uniq_staff_pay_period"),
        ),
        migrations.AddConstraint(
            model_name="staffpayrun",
            constraint=models.CheckConstraint(condition=Q(gross_amount__gt=0),name="staff_pay_gross_positive"),
        ),
        migrations.AddConstraint(
            model_name="staffpayrun",
            constraint=models.CheckConstraint(condition=Q(deductions__gte=0),name="staff_pay_deductions_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="staffpaydisbursement",
            constraint=models.UniqueConstraint(fields=("school","idempotency_key"),name="uniq_staff_pay_idempotency"),
        ),
        migrations.AddConstraint(
            model_name="staffpaydisbursement",
            constraint=models.CheckConstraint(condition=Q(amount__gt=0),name="staff_disbursement_positive"),
        ),
        migrations.RunPython(restrict_tables,migrations.RunPython.noop),
        migrations.RunPython(grant_standard_roles,migrations.RunPython.noop),
    ]
