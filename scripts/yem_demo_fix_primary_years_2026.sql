-- Align only the generated Complexe Les 8 DEMO26 primary records with YEM's
-- existing five-year primary taxonomy. Historical/real school data untouched.
-- Legacy CE1 and CE2 are two classroom divisions of the SAME 3e année level.
-- Atomic and idempotent; all active pupils/courses/grades/attendance remain linked
-- to their original classroom UUIDs. No grading or financial figures are altered.
DO $fix$
DECLARE
  sid uuid := '96f99506-a8d6-4dab-b292-4076800c9bd7';
  target_year_id uuid; primary_id uuid; old_count integer;
  item record; demo_level_id uuid; classroom_id uuid; new_level_id uuid;
  scope_new jsonb; class_old text; class_new text; level_new text;
  settings_id uuid; report_count integer;
BEGIN
  PERFORM pg_advisory_xact_lock(20261109);
  SELECT id INTO target_year_id FROM institutions_academicyear
    WHERE school_id=sid AND code='2026-2027';
  SELECT id INTO primary_id FROM institutions_academiccycle
    WHERE school_id=sid AND code='primaire';
  IF target_year_id IS NULL OR primary_id IS NULL THEN
    RAISE EXCEPTION 'The targeted demo school/year/primary cycle was not found';
  END IF;

  SELECT count(*) INTO old_count FROM institutions_academiclevel
    WHERE school_id=sid AND cycle_id=primary_id
      AND code IN ('cp1','cp2','ce1','ce2','cm1','cm2');
  IF old_count=0 AND
    (SELECT count(*) FROM institutions_academiclevel
      WHERE school_id=sid AND cycle_id=primary_id
        AND code IN ('1re-annee','2e-annee','3e-annee','4e-annee','5e-annee'))=5
  THEN
    RAISE NOTICE 'The five-year naming is already installed: no changes';
    RETURN;
  END IF;
  IF old_count<>6 OR EXISTS(
    SELECT 1 FROM institutions_academiclevel
    WHERE school_id=sid AND cycle_id=primary_id
      AND code IN ('1re-annee','2e-annee','3e-annee','4e-annee','5e-annee')
  ) THEN RAISE EXCEPTION 'Unexpected primary levels; refuse modification'; END IF;

  -- All six old levels/classes must be the exact records created by our seed.
  FOR item IN SELECT * FROM (VALUES
     ('cp1','1re-annee','1re année','a',1),
     ('cp2','2e-annee','2e année','a',2),
     ('ce1','3e-annee','3e année','a',3),
     ('ce2','3e-annee','3e année','b',3),
     ('cm1','4e-annee','4e année','a',4),
     ('cm2','5e-annee','5e année','a',5)
  ) AS v(old_code,new_code,new_name,division,level_order)
  LOOP
    demo_level_id := md5('YEM-DEMO-2026:level:CES8:'||item.old_code)::uuid;
    classroom_id := md5('YEM-DEMO-2026:class:CES8:'||item.old_code)::uuid;
    class_old := 'demo26-'||item.old_code||'-a';
    class_new := 'demo26-'||item.new_code||'-'||item.division;
    IF NOT EXISTS (
       SELECT 1 FROM institutions_academiclevel
       WHERE id=demo_level_id AND school_id=sid AND cycle_id=primary_id AND code=item.old_code
    ) OR NOT EXISTS (
       SELECT 1 FROM institutions_academicclass
       WHERE id=classroom_id AND school_id=sid AND year_id=target_year_id
          AND level_id=demo_level_id AND code=class_old
    ) THEN RAISE EXCEPTION 'Refusing to modify unrecognized level/class: %',item.old_code;
    END IF;
    IF EXISTS (
       SELECT 1 FROM institutions_academicclass
       WHERE school_id=sid AND year_id=target_year_id AND code=class_new
    ) THEN RAISE EXCEPTION 'New target class code already exists: %',class_new; END IF;
    settings_id:=md5('YEM-DEMO-2026:settings:CES8:'||class_old)::uuid;
    IF NOT EXISTS (
      SELECT 1 FROM institutions_schoolsetting
      WHERE id=settings_id AND school_id=sid
       AND scope->>'cycle'='primaire' AND scope->>'class'=class_old
       AND scope->>'level'=item.old_code
    ) THEN RAISE EXCEPTION 'Unrecognized class policy for %',class_old; END IF;
    IF EXISTS (
       SELECT 1 FROM institutions_enrollment e
       JOIN institutions_academicclass c ON c.id=e.classroom_id
       JOIN institutions_student s ON s.id=e.student_id
       WHERE c.id=classroom_id AND s.student_code NOT LIKE 'DEMO26-CES8-%'
    ) THEN RAISE EXCEPTION 'Real/other pupil found in %: do not alter class',class_old; END IF;
  END LOOP;
  -- Rename the five retained levels first; the CE2 legacy level is merged.
  FOR item IN SELECT * FROM (VALUES
    ('cp1','1re-annee','1re année',1),
    ('cp2','2e-annee','2e année',2),
    ('ce1','3e-annee','3e année',3),
    ('cm1','4e-annee','4e année',4),
    ('cm2','5e-annee','5e année',5)
  ) AS v(old_code,new_code,new_name,level_order)
  LOOP
    UPDATE institutions_academiclevel
    SET code=item.new_code,name=item.new_name,"order"=item.level_order,
      revision=revision+1
    WHERE id=md5('YEM-DEMO-2026:level:CES8:'||item.old_code)::uuid
      AND school_id=sid AND cycle_id=primary_id;
  END LOOP;

  FOR item IN SELECT * FROM (VALUES
    ('cp1','1re-annee','1re année','a'),
    ('cp2','2e-annee','2e année','a'),
    ('ce1','3e-annee','3e année','a'),
    ('ce2','3e-annee','3e année','b'),
    ('cm1','4e-annee','4e année','a'),
    ('cm2','5e-annee','5e année','a')
  ) AS v(old_code,new_code,new_name,division)
  LOOP
    class_old:='demo26-'||item.old_code||'-a';
    class_new:='demo26-'||item.new_code||'-'||item.division;
    -- Actual level UUIDs are derived from their original code before renaming!
    new_level_id:=md5('YEM-DEMO-2026:level:CES8:'||
      CASE item.new_code WHEN '1re-annee' THEN 'cp1'
        WHEN '2e-annee' THEN 'cp2' WHEN '3e-annee' THEN 'ce1'
        WHEN '4e-annee' THEN 'cm1' ELSE 'cm2' END)::uuid;
    UPDATE institutions_academicclass SET
       level_id=new_level_id,
       code=class_new, name=item.new_name||' '||upper(item.division)||' (démo)',
       revision=revision+1
    WHERE id=md5('YEM-DEMO-2026:class:CES8:'||item.old_code)::uuid
      AND school_id=sid AND year_id=target_year_id;
    scope_new:=jsonb_build_object('year','2026-2027','cycle','primaire',
                  'level',item.new_code,'class',class_new);
    UPDATE institutions_schoolsetting SET
      scope=scope_new,scope_key=format(
       '{"class":"%s","cycle":"primaire","level":"%s","year":"2026-2027"}',
       class_new,item.new_code),revision=revision+1,updated_at=NOW()
    WHERE id=md5('YEM-DEMO-2026:settings:CES8:'||class_old)::uuid
      AND school_id=sid;
    -- Only our synthetic DRAFT reports may be refreshed; published reports
    -- remain untouched. Class identity/classroom UUID remains the same.
    UPDATE institutions_schoolreport r SET
      snapshot=jsonb_set(
        jsonb_set(r.snapshot,'{class,name}',
          to_jsonb(item.new_name||' '||upper(item.division)||' (démo)')),
        '{layers}',jsonb_build_array(jsonb_build_object(
          'scope',scope_new,'revision',2))
      ),revision=revision+1
    FROM institutions_enrollment e
    JOIN institutions_student st ON st.id=e.student_id
    WHERE r.enrollment_id=e.id
      AND e.classroom_id=md5('YEM-DEMO-2026:class:CES8:'||item.old_code)::uuid
      AND e.school_id=sid AND r.school_id=sid
      AND st.student_code LIKE 'DEMO26-CES8-%'
      AND r.status='draft';
  END LOOP;

  -- CE2 has been merged into the third-year level: remove only the now
  -- unreferenced exact synthetic level (never a real establishment level).
  DELETE FROM institutions_academiclevel
   WHERE id=md5('YEM-DEMO-2026:level:CES8:ce2')::uuid
     AND school_id=sid AND cycle_id=primary_id AND code='ce2'
     AND NOT EXISTS(SELECT 1 FROM institutions_academicclass
        WHERE level_id=md5('YEM-DEMO-2026:level:CES8:ce2')::uuid)
     AND NOT EXISTS(SELECT 1 FROM institutions_academictrack
        WHERE level_id=md5('YEM-DEMO-2026:level:CES8:ce2')::uuid);
  IF EXISTS(SELECT 1 FROM institutions_academiclevel
      WHERE school_id=sid AND cycle_id=primary_id
      AND code IN ('cp1','cp2','ce1','ce2','cm1','cm2')) THEN
    RAISE EXCEPTION 'Old primary codes remain; abort transaction';
  END IF;
  IF (SELECT count(*) FROM institutions_academiclevel
      WHERE school_id=sid AND cycle_id=primary_id AND active) <> 5 THEN
    RAISE EXCEPTION 'Expected exactly five active primary levels';
  END IF;
END
$fix$;
