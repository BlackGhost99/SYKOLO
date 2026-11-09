-- YEM fictitious classroom teaching, attendance, scores and timetable.
-- Run AFTER yem_demo_seed_base_2026.sql. Inserts only; repeatable safely.
DO $seed$
DECLARE
  s record; c record; e record; subidx integer; sessionidx integer;
  sch uuid; yr uuid; period_id uuid; subj uuid; crs uuid; staff_id uuid;
  assignment_id uuid; instructor_id uuid; asmt_id uuid; draft_id uuid;
  teacher_index integer; slot_id uuid; grade_score integer;
  score_pct numeric; grade_label text; absent boolean; pos int;
  selected_subject text; source_class_code text; policy jsonb; setting_value jsonb; scope jsonb;
  scope_key text; att_id uuid; profile_id uuid;
BEGIN
  PERFORM pg_advisory_xact_lock(20261109);
  policy := '{
    "schemaVersion":1,"name":"Barème de démonstration (/20)",
    "scale":{"kind":"numeric","max":20},
    "precision":2,"missing":"exclude",
    "bands":[
      {"min":0,"value":20,"label":"Insuffisant"},
      {"min":50,"value":55,"label":"Passable"},
      {"min":60,"value":65,"label":"Assez bien"},
      {"min":70,"value":75,"label":"Bien"},
      {"min":80,"value":90,"label":"Très bien"}
    ],
    "report":{"showScore":true,"showLabel":true},
    "notification":{"enabled":false,"below":40,"message":"Résultat scolaire à surveiller"}
  }'::jsonb;
  setting_value := jsonb_build_object(
    'grading',policy,
    'bulletin',jsonb_build_object(
      'title','Bulletin de démonstration — DOCUMENT FICTIF',
      'show_score',true,'show_label',true,'precision',2
    ),
    'attendance',jsonb_build_object('statuses',jsonb_build_array(
      jsonb_build_object('code','present','label','Présent','group','present'),
      jsonb_build_object('code','absent','label','Absent','group','absent'),
      jsonb_build_object('code','retard','label','En retard','group','late')
    ))
  );
  FOR s IN SELECT * FROM jsonb_to_recordset('[
    {"id":"96f99506-a8d6-4dab-b292-4076800c9bd7","tag":"CES8","kind":"complexe","n":1},
    {"id":"b8ccefc7-c993-49f3-b2f3-70e59ca7db20","tag":"LP1","kind":"lycee","n":2},
    {"id":"eae64fe7-bac2-4b94-a999-4f278a33ef2a","tag":"LP2","kind":"lycee","n":3}
  ]'::jsonb) AS x(id uuid,tag text,kind text,n int)
  LOOP
    sch := s.id;
    SELECT id INTO yr FROM institutions_academicyear
      WHERE school_id=sch AND code='2026-2027';
    SELECT id INTO period_id FROM institutions_academicperiod
      WHERE school_id=sch AND year_id=yr AND code='demo26-trim1';
    IF yr IS NULL OR period_id IS NULL THEN
      RAISE EXCEPTION 'Missing demonstration academic year/period at %',s.tag;
    END IF;
    FOR c IN SELECT a.id,a.code,a.name,lev.code AS level_code,
           cy.code AS cycle_code,
           ROW_NUMBER() OVER(ORDER BY CASE WHEN a.code LIKE 'demo26-%' THEN 0 ELSE 1 END,a.code,a.id)::integer AS idx
       FROM institutions_academicclass a
       JOIN institutions_academiclevel lev ON lev.id=a.level_id
       JOIN institutions_academiccycle cy ON cy.id=lev.cycle_id
       WHERE a.school_id=sch AND a.year_id=yr
         AND (a.code LIKE 'demo26-%' OR a.code LIKE 'demo-%') AND a.active
       ORDER BY CASE WHEN a.code LIKE 'demo26-%' THEN 0 ELSE 1 END,a.code,a.id
    LOOP
      -- Retain the UUIDs/assessments created under older demo class codes;
      -- only the visible names and settings scope change.
      source_class_code := CASE WHEN s.tag='CES8' THEN
        CASE c.code
          WHEN 'demo26-1re-annee-a' THEN 'demo26-cp1-a'
          WHEN 'demo26-2e-annee-a' THEN 'demo26-cp2-a'
          WHEN 'demo26-3e-annee-a' THEN 'demo26-ce1-a'
          WHEN 'demo26-3e-annee-b' THEN 'demo26-ce2-a'
          WHEN 'demo26-4e-annee-a' THEN 'demo26-cm1-a'
          WHEN 'demo26-5e-annee-a' THEN 'demo26-cm2-a'
          ELSE c.code END
        ELSE c.code END;
      scope := jsonb_build_object(
        'year','2026-2027','cycle',c.cycle_code,
        'level',c.level_code,'class',c.code
      );
      scope_key := format(
        '{"class":"%s","cycle":"%s","level":"%s","year":"2026-2027"}',
        c.code,c.cycle_code,c.level_code
      );
      profile_id := md5('YEM-DEMO-2026:settings:'||s.tag||':'||source_class_code)::uuid;
      INSERT INTO institutions_schoolsetting
        (id,school_id,scope_key,scope,values,revision,updated_at)
      VALUES(profile_id,sch,scope_key,scope,setting_value,1,NOW())
      ON CONFLICT DO NOTHING;

      FOR subidx IN 1..3 LOOP
        IF c.cycle_code='prescolaire' THEN
          selected_subject := (ARRAY['langage','ecriture','eveil'])[subidx];
        ELSIF c.cycle_code='primaire' THEN
          selected_subject := (ARRAY['francais','maths','eveil'])[subidx];
        ELSE
          selected_subject := (ARRAY['francais','maths','histoire_geo'])[subidx];
        END IF;
        SELECT id INTO subj FROM institutions_subject
         WHERE school_id=sch AND code='demo26-'||selected_subject;
        IF subj IS NULL THEN
          RAISE EXCEPTION 'Missing subject % for %',selected_subject,s.tag;
        END IF;
        crs := md5('YEM-DEMO-2026:course:'||s.tag||':'||source_class_code||':'||subidx)::uuid;
        INSERT INTO institutions_courseoffering
          (id,school_id,year_id,classroom_id,subject_id,coefficient,active,revision)
        VALUES(crs,sch,yr,c.id,subj,CASE WHEN subidx=2 THEN 3 ELSE 2 END,true,1)
        ON CONFLICT DO NOTHING;

        staff_id := md5('YEM-DEMO-2026:staff:'||s.tag||':'||subidx)::uuid;
        IF NOT EXISTS(SELECT 1 FROM institutions_staffrecord WHERE id=staff_id AND school_id=sch)
        THEN RAISE EXCEPTION 'Missing teacher % for %',subidx,s.tag; END IF;
        assignment_id := md5('YEM-DEMO-2026:staffassign:'||s.tag||':'||source_class_code||':'||subidx)::uuid;
        INSERT INTO institutions_staffassignment
         (id,school_id,staff_id,year_id,classroom_id,duty,active,revision)
        VALUES(assignment_id,sch,staff_id,yr,c.id,'enseignant',true,1)
        ON CONFLICT DO NOTHING;
        instructor_id := md5('YEM-DEMO-2026:instructor:'||s.tag||':'||source_class_code||':'||subidx)::uuid;
        INSERT INTO institutions_courseinstructor
         (id,school_id,course_id,staff_assignment_id,active,revision)
        VALUES(instructor_id,sch,crs,assignment_id,true,1)
        ON CONFLICT DO NOTHING;

        slot_id := md5('YEM-DEMO-2026:slot:'||s.tag||':'||
           (1+((c.idx-1)/5))::text)::uuid;
        INSERT INTO institutions_timetableentry
          (id,school_id,year_id,classroom_id,course_id,instructor_id,
           slot_id,room_id,weekday,effective_from,effective_to,
           active,revision,created_by_id,updated_at)
        VALUES(md5('YEM-DEMO-2026:timetable:'||s.tag||':'||source_class_code||':'||subidx)::uuid,
          sch,yr,c.id,crs,instructor_id,slot_id,NULL,
          ((c.idx-1+subidx-1)%5),DATE '2026-10-05',DATE '2027-06-30',
          true,1,NULL,NOW())
        ON CONFLICT DO NOTHING;

        asmt_id := md5('YEM-DEMO-2026:assessment:'||s.tag||':'||source_class_code||':'||subidx)::uuid;
        INSERT INTO institutions_assessment
          (id,school_id,course_id,period_id,name,kind,assessment_date,
           weight,policy_snapshot,policy_layers,active,published,revision,created_at)
        VALUES(asmt_id,sch,crs,period_id,
          'Contrôle continu 1 (démo)','controle',DATE '2026-11-04',
          1,policy,'[]'::jsonb,true,true,1,NOW())
        ON CONFLICT DO NOTHING;

        -- A second unpublished evaluation remains available for grade-entry tests.
        IF subidx=1 THEN
          draft_id := md5('YEM-DEMO-2026:draftassessment:'||s.tag||':'||source_class_code)::uuid;
          INSERT INTO institutions_assessment
            (id,school_id,course_id,period_id,name,kind,assessment_date,
             weight,policy_snapshot,policy_layers,active,published,revision,created_at)
          VALUES(draft_id,sch,crs,period_id,
            'Évaluation 2 à saisir (démo)','devoir',DATE '2026-11-06',
            1,policy,'[]'::jsonb,true,false,1,NOW())
          ON CONFLICT DO NOTHING;
        END IF;

        FOR e IN SELECT en.id,st.student_code,
              right(st.student_code,3)::integer AS n
          FROM institutions_enrollment en
          JOIN institutions_student st ON st.id=en.student_id
         WHERE en.school_id=sch AND en.year_id=yr AND en.classroom_id=c.id
           AND st.student_code LIKE 'DEMO26-%'
        LOOP
          grade_score := 8 + ((e.n*3 + subidx*4 + s.n)%12);
          score_pct := grade_score*5;
          grade_label := CASE
            WHEN score_pct>=80 THEN 'Très bien'
            WHEN score_pct>=70 THEN 'Bien'
            WHEN score_pct>=60 THEN 'Assez bien'
            WHEN score_pct>=50 THEN 'Passable'
            ELSE 'Insuffisant' END;
          INSERT INTO institutions_assessmentgrade
            (id,school_id,assessment_id,enrollment_id,score,
             feedback,status,percent,label,revision,author_id,updated_at)
          VALUES(md5('YEM-DEMO-2026:grade:'||s.tag||':'||source_class_code||':'||subidx||':'||e.n)::uuid,
            sch,asmt_id,e.id,to_jsonb(grade_score),
            'Résultat fictif pour tester YEM','calculated',score_pct,
            grade_label,1,NULL,NOW())
          ON CONFLICT DO NOTHING;
        END LOOP;
      END LOOP;

      FOR sessionidx IN 1..2 LOOP
        att_id:=md5('YEM-DEMO-2026:attendance:'||s.tag||':'||source_class_code||':'||sessionidx)::uuid;
        INSERT INTO institutions_attendancesession
          (id,school_id,classroom_id,attendance_date,slot,label,revision,
           closed_at,created_by_id,closed_by_id,created_at)
        VALUES(att_id,sch,c.id,DATE '2026-11-02'+(sessionidx-1),
          'demo26-appel-'||sessionidx,
          'Appel du matin · démonstration '||sessionidx,1,
          NULL,NULL,NULL,NOW())
        ON CONFLICT DO NOTHING;
        FOR e IN SELECT en.id,st.student_code,
                 right(st.student_code,3)::integer AS n
          FROM institutions_enrollment en
          JOIN institutions_student st ON st.id=en.student_id
         WHERE en.school_id=sch AND en.year_id=yr AND en.classroom_id=c.id
           AND st.student_code LIKE 'DEMO26-%'
        LOOP
          absent := ((e.n+s.n+sessionidx)%5=0);
          INSERT INTO institutions_attendancemark
            (id,school_id,session_id,enrollment_id,status_code,
             status_label,status_group,note,justification,justified,
             revision,updated_by_id,updated_at)
          VALUES(md5('YEM-DEMO-2026:mark:'||s.tag||':'||source_class_code||':'||sessionidx||':'||e.n)::uuid,
             sch,att_id,e.id,CASE WHEN absent THEN 'absent' ELSE 'present' END,
             CASE WHEN absent THEN 'Absent' ELSE 'Présent' END,
             CASE WHEN absent THEN 'absent' ELSE 'present' END,
             CASE WHEN absent THEN 'Absence fictive (démo)' ELSE '' END,
             CASE WHEN absent AND e.n%2=0 THEN 'Justification fictive' ELSE '' END,
             (absent AND e.n%2=0),
             1,NULL,NOW())
          ON CONFLICT DO NOTHING;
        END LOOP;
      END LOOP;
    END LOOP;
  END LOOP;
END
$seed$;