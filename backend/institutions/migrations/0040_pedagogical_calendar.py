"""Calendrier pédagogique indépendant des périodes, sans migration des anciens dossiers."""
import uuid

from django.db import migrations, models
import django.db.models.deletion


def protect_calendar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = apps.get_model("institutions", "PedagogicalCalendarEvent")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        # Table créée après la stratégie RLS générale (migration 0029).
        cursor.execute('ALTER TABLE "' + table + '" ENABLE ROW LEVEL SECURITY')
        cursor.execute("""
            CREATE FUNCTION yem_closed_pedagogical_calendar() RETURNS trigger
            LANGUAGE plpgsql AS $guard$
            DECLARE target_year uuid;
            BEGIN
                IF TG_OP = 'DELETE' THEN
                    target_year := OLD.year_id;
                ELSE
                    target_year := NEW.year_id;
                END IF;
                IF EXISTS (
                    SELECT 1 FROM institutions_academicyear
                    WHERE id = target_year AND (status = 'closed' OR active = false)
                ) THEN
                    RAISE EXCEPTION 'Année scolaire clôturée : calendrier verrouillé'
                        USING ERRCODE = '23514';
                END IF;
                IF TG_OP = 'UPDATE' AND EXISTS (
                    SELECT 1 FROM institutions_academicyear
                    WHERE id = OLD.year_id AND (status = 'closed' OR active = false)
                ) THEN
                    RAISE EXCEPTION 'Calendrier historique verrouillé'
                        USING ERRCODE = '23514';
                END IF;
                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $guard$
        """)
        cursor.execute('CREATE TRIGGER yem_calendar_year_guard BEFORE INSERT OR UPDATE OR DELETE ON "' +
                       table + '" FOR EACH ROW EXECUTE FUNCTION yem_closed_pedagogical_calendar()')


def unprotect_calendar(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = apps.get_model("institutions", "PedagogicalCalendarEvent")._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TRIGGER IF EXISTS yem_calendar_year_guard ON "' + table + '"')
        cursor.execute("DROP FUNCTION IF EXISTS yem_closed_pedagogical_calendar()")


class Migration(migrations.Migration):
    dependencies = [("institutions", "0039_immutable_year_closure")]

    operations = [
        migrations.CreateModel(
            name="PedagogicalCalendarEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("title", models.CharField(max_length=160)),
                ("kind", models.CharField(
                    max_length=24, default="autre",
                    choices=[
                        ("rentree", "Rentrée"), ("cours", "Cours et reprise"),
                        ("evaluation", "Évaluations / arrêt des notes"),
                        ("bulletins", "Bulletins / conseils"),
                        ("vacances", "Vacances et congés"),
                        ("examen", "Examens / concours"),
                        ("ferie", "Jour férié"), ("reunion", "Réunion / activité"),
                        ("autre", "Autre"),
                    ],
                )),
                ("scope", models.CharField(
                    max_length=24, default="all",
                    choices=[
                        ("all", "Tous les cycles"), ("prescolaire", "Maternelle"),
                        ("primaire", "Primaire"), ("college", "Collège"),
                        ("lycee_general", "Lycée général"),
                        ("lycee_technique", "Lycée technique"),
                    ],
                )),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("description", models.CharField(max_length=500, blank=True, default="")),
                ("source", models.CharField(
                    max_length=16, default="school",
                    choices=[("school", "Établissement"), ("official", "Référence nationale")],
                )),
                ("source_url", models.URLField(max_length=500, blank=True, default="")),
                ("active", models.BooleanField(default=True)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("school", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="calendar_events", to="institutions.school",
                )),
                ("year", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="calendar_events", to="institutions.academicyear",
                )),
            ],
            options={"ordering": ["start_date", "end_date", "title"]},
        ),
        migrations.RunPython(protect_calendar, unprotect_calendar),
    ]
