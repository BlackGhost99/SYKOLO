-- YEM: 45 genuine SchoolReport records built from published simulated grades.
-- Every report is deliberately a DRAFT headed "DOCUMENT FICTIF".
-- Their PDF exports use the existing server-side bulletin generator.
DO $reports$
DECLARE
  r record; co record; period_row record; st record; school_row record;
  snapshot jsonb; subjects jsonb; sources jsonb; result_item jsonb;
  overall jsonb; policy jsonb; scope_json jsonb; layers jsonb; template jsonb;
  pct numeric; overall_sum numeric; weight_sum numeric;
  grade_count integer; assessment_count integer; evidence_count integer;
  value_text text; grade_label text; class_name text; year_name text;
BEGIN
  PERFORM pg_advisory_xact_lock(20261109);
  FOR r IN
    SELECT en.id AS enrollment_id,en.school_id,en.year_id,
      en.classroom_id,en.student_id,cl.code AS class_code,
      cl.name AS class_name,cl.level_id,lev.code AS level_code,
      cy.code AS cycle_code,yr.name AS year_name,
      yr.code AS year_code,st.student_code,st.first_name,st.last_name,
      st.identity_id,sch.name AS school_name,sch.short_name AS school_short_name,
      p.id AS period_id,p.name AS period_name,ss.scope,ss.values AS config,
      ss.revision AS setting_revision
    FROM institutions_enrollment en
    JOIN institutions_student st ON st.id=en.student_id
    JOIN institutions_academicclass cl ON cl.id=en.classroom_id
    JOIN institutions_academiclevel lev ON lev.id=cl.level_id
    JOIN institutions_academiccycle cy ON cy.id=lev.cycle_id
    JOIN institutions_academicyear yr ON yr.id=en.year_id
    JOIN institutions_school sch ON sch.id=en.school_id
    JOIN institutions_academicperiod p
      ON p.school_id=en.school_id AND p.year_id=en.year_id
      AND p.code='demo26-trim1'
    JOIN institutions_schoolsetting ss
      ON ss.school_id=en.school_id
      AND ss.scope->>'class'=cl.code
      AND ss.scope->>'year'=yr.code
      AND ss.scope->>'level'=lev.code
      AND ss.scope->>'cycle'=cy.code
    WHERE st.student_code LIKE 'DEMO26-%' AND en.active
      AND yr.code='2026-2027'
    ORDER BY sch.name,st.student_code
  LOOP
    policy:=r.config->'grading';
    template:=jsonb_build_object(
      'title','Bulletin de démonstration — DOCUMENT FICTIF',
      'precision',2,'show_score',true,'show_label',true,
      'show_rank',false,'missing_entry','exclude'
    );
    layers:=jsonb_build_array(jsonb_build_object(
      'scope',r.scope,'revision',r.setting_revision
    ));
    subjects:='[]'::jsonb; sources:='[]'::jsonb;
    overall_sum:=0;weight_sum:=0;grade_count:=0;
    FOR co IN
      SELECT course.id AS course_id,course.coefficient,
        subj.name AS subject_name,asmt.id AS assessment_id,
        asmt.revision AS assessment_revision,agr.id AS grade_id,
        agr.revision AS grade_revision,agr.percent,agr.label,
        asmt.weight
      FROM institutions_courseoffering course
      JOIN institutions_subject subj ON subj.id=course.subject_id
      JOIN institutions_assessment asmt
        ON asmt.course_id=course.id AND asmt.published
        AND asmt.period_id=r.period_id
      LEFT JOIN institutions_assessmentgrade agr
        ON agr.assessment_id=asmt.id AND agr.enrollment_id=r.enrollment_id
      WHERE course.school_id=r.school_id AND course.year_id=r.year_id
        AND course.classroom_id=r.classroom_id
        AND asmt.name='Contrôle continu 1 (démo)'
      ORDER BY subj.name,course.id,asmt.id
    LOOP
      sources := sources || jsonb_build_array(jsonb_build_object(
        'assessment',co.assessment_id::text,
        'revision',co.assessment_revision,
        'grade',co.grade_id::text,
        'grade_revision',co.grade_revision
      ));
      IF co.percent IS NULL THEN CONTINUE; END IF;
      grade_count:=grade_count+1;
      pct:=co.percent;
      grade_label := CASE
        WHEN pct>=80 THEN 'Très bien'
        WHEN pct>=70 THEN 'Bien'
        WHEN pct>=60 THEN 'Assez bien'
        WHEN pct>=50 THEN 'Passable'
        ELSE 'Insuffisant' END;
      result_item:=jsonb_build_object(
        'status','calculated',
        'percent',to_char(pct,'FM999990.00'),
        'score',to_char(pct/5,'FM999990.00'),
        'label',grade_label
      );
      subjects:=subjects||jsonb_build_array(jsonb_build_object(
        'course',co.course_id::text,
        'subject',co.subject_name,
        'coefficient',co.coefficient::text,
        'result',result_item,
        'assessments',1
      ));
      overall_sum:=overall_sum+(pct*co.coefficient);
      weight_sum:=weight_sum+co.coefficient;
    END LOOP;
    IF grade_count=0 THEN
       RAISE EXCEPTION 'Missing grades for demonstration enrollment %',r.student_code;
    END IF;
    pct:=round(overall_sum/weight_sum,2);
    grade_label:=CASE
      WHEN pct>=80 THEN 'Très bien'
      WHEN pct>=70 THEN 'Bien'
      WHEN pct>=60 THEN 'Assez bien'
      WHEN pct>=50 THEN 'Passable'
      ELSE 'Insuffisant' END;
    overall:=jsonb_build_object(
      'status','calculated',
      'percent',to_char(pct,'FM999990.00'),
      'score',to_char(pct/5,'FM999990.00'),
      'label',grade_label
    );
    snapshot:=jsonb_build_object(
      'created_at',NOW()::text,
      'school',jsonb_build_object('id',r.school_id::text,
          'name',r.school_name,'short_name',r.school_short_name),
      'student',jsonb_build_object('id',r.student_id::text,
          'code',r.student_code,
          'matricule_yem','YEM-'||replace(upper(r.identity_id::text),'-',''),
          'first_name',r.first_name,'last_name',r.last_name),
      'class',jsonb_build_object('id',r.classroom_id::text,'name',r.class_name),
      'year',jsonb_build_object('id',r.year_id::text,'name',r.year_name),
      'period',jsonb_build_object('id',r.period_id::text,'name',r.period_name),
      'subjects',subjects,
      'overall',overall,
      'policy_snapshot',policy,
      'template',template,
      'layers',layers,
      'sources',sources,
      'recorded_grade_count',grade_count
    );
    INSERT INTO institutions_schoolreport
      (id,school_id,enrollment_id,year_id,period_id,
       period_key,status,snapshot,revision,prepared_by_id,created_at,published_at)
    VALUES(md5('YEM-DEMO-2026:report:'||r.student_code)::uuid,
       r.school_id,r.enrollment_id,r.year_id,r.period_id,r.period_id::text,
       'draft',snapshot,1,NULL,NOW(),NULL)
    ON CONFLICT DO NOTHING;
  END LOOP;
END
$reports$;