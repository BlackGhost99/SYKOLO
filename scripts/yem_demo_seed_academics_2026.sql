-- YEM extended synthetic demonstration: courses, timetable, grades, attendance, printable reports.
-- Run only after scripts/yem_demo_seed_base_2026.sql. Insert-only and repeatable.
DO $demo$
DECLARE
  s record; cl record; x record; en record;
  sch uuid; yr uuid; periodid uuid; courseid uuid; staffid uuid; assignmentid uuid;
  teacherid uuid; subjectid uuid; assessmentid uuid; gradeid uuid; sessionid uuid; slotid uuid;
  course_pos integer; class_pos integer; staff_pos integer; slot_pos integer;
  student_idx integer; grade_score integer; grade_percent integer; grade_label text;
  subject_list text[]; policy jsonb; enrolled_on date;
  doc jsonb; subject_rows jsonb; source_rows jsonb; overall_score numeric; totalgrades int;
  school_name text; school_short_label text;
  demo_schools jsonb := '[
    {"id":"96f99506-a8d6-4dab-b292-4076800c9bd7","tag":"CES8","kind":"complexe","n":1},
    {"id":"b8ccefc7-c993-49f3-b2f3-70e59ca7db20","tag":"LP1","kind":"lycee","n":2},
    {"id":"eae64fe7-bac2-4b94-a999-4f278a33ef2a","tag":"LP2","kind":"lycee","n":3}
  ]'::jsonb;
  grading jsonb := '{
    "schemaVersion":1,"name":"Barème fictif de démonstration sur 20",
    "scale":{"kind":"numeric","max":20},
    "precision":2,"missing":"exclude",
    "bands":[
      {"min":0,"value":25,"label":"Insuffisant"},
      {"min":50,"value":55,"label":"Passable"},
      {"min":60,"value":65,"label":"Assez bien"},
      {"min":70,"value":75,"label":"Bien"},
      {"min":85,"value":90,"label":"Très bien"}
    ],
    "report":{"showScore":true,"showLabel":true},
    "notification":{"enabled":false,"below":50,"message":"Note à suivre"}
  }'::jsonb;
BEGIN
  PERFORM pg_advisory_xact_lock(20261109);
  FOR s IN SELECT * FROM jsonb_to_recordset(demo_schools)
       AS z(id uuid,tag text,kind text,n int)
  LOOP
    sch:=s.id;
    SELECT id INTO yr FROM public.institutions_academicyear
      WHERE school_id=sch AND code='2026-2027' LIMIT 1;
    IF yr IS NULL THEN RAISE EXCEPTION 'Seed base missing in school %',s.tag; END IF;
    SELECT id INTO periodid FROM public.institutions_academicperiod
      WHERE school_id=sch AND year_id=yr AND code='demo26-trim1' LIMIT 1;
    IF periodid IS NULL THEN RAISE EXCEPTION 'Demo trimester missing in %',s.tag; END IF;
    SELECT name,short_name INTO school_name,school_short_label FROM public.institutions_school WHERE id=sch;
    class_pos:=0;
    FOR cl IN
      SELECT c.id,c.code,c.name, c.level_id,
        lv.code AS level_code, cy.code AS cycle_code
      FROM public.institutions_academicclass c
      JOIN public.institutions_academiclevel lv ON lv.id=c.level_id
      JOIN public.institutions_academiccycle cy ON cy.id=lv.cycle_id
      WHERE c.school_id=sch AND c.year_id=yr AND c.active
        AND (c.code LIKE 'demo26-%' OR c.code LIKE 'demo-%')
      ORDER BY c.code,c.id
    LOOP
      class_pos:=class_pos+1;
      -- Only configure fictional classes; never change real school-wide settings.
      INSERT INTO public.institutions_schoolsetting
        (id,school_id,scope_key,scope,values,revision,updated_at)
      VALUES(
        md5('YEM-DEMO-2026:grading:'||s.tag||':'||cl.code)::uuid,sch,
        '{"class":"'||cl.code||'","year":"2026-2027"}',
        jsonb_build_object('class',cl.code,'year','2026-2027'),
        jsonb_build_object('grading',grading,
          'bulletin',jsonb_build_object('title','BULLETIN FICTIF - DEMONSTRATION YEM',
            'precision',2,'show_score',true,'show_label',true,
            'show_rank',false,'missing_entry','exclude')),
        1,NOW()
      ) ON CONFLICT DO NOTHING;
      subject_list:=
        CASE WHEN cl.cycle_code='prescolaire' THEN ARRAY['langage','ecriture','eveil']
             WHEN cl.cycle_code='primaire' THEN ARRAY['francais','maths','lecture','eveil']
             ELSE ARRAY['francais','maths','anglais','histoire_geo','svt']
        END;
      FOR course_pos IN 1..array_length(subject_list,1)
      LOOP
        subjectid:=md5('YEM-DEMO-2026:subject:'||s.tag||':'||subject_list[course_pos])::uuid;
        SELECT id INTO subjectid FROM public.institutions_subject
          WHERE school_id=sch AND code='demo26-'||subject_list[course_pos] LIMIT 1;
        IF subjectid IS NULL THEN RAISE EXCEPTION 'Subject missing in school %',s.tag; END IF;
        courseid:=md5('YEM-DEMO-2026:course:'||cl.id::text||':'||subject_list[course_pos])::uuid;
        INSERT INTO public.institutions_courseoffering
          (id,school_id,year_id,classroom_id,subject_id,coefficient,active,revision)
        VALUES(courseid,sch,yr,cl.id,subjectid,
          CASE WHEN subject_list[course_pos] IN ('francais','maths') THEN 4
               WHEN subject_list[course_pos] IN ('anglais','lecture','langage') THEN 3
               ELSE 2 END,true,1)
        ON CONFLICT DO NOTHING;
        -- Prefer actual unique course if a prior seeded/real offering for the same subject exists.
        SELECT id INTO courseid FROM public.institutions_courseoffering
          WHERE school_id=sch AND year_id=yr AND classroom_id=cl.id AND subject_id=subjectid LIMIT 1;
        staff_pos:=((class_pos + course_pos - 2) % 6) + 1;
        staffid:=md5('YEM-DEMO-2026:staff:'||s.tag||':'||staff_pos)::uuid;
        assignmentid:=md5('YEM-DEMO-2026:assignment:'||cl.id::text||':'||staff_pos)::uuid;
        INSERT INTO public.institutions_staffassignment
          (id,school_id,staff_id,year_id,classroom_id,duty,active,revision)
        VALUES(assignmentid,sch,staffid,yr,cl.id,'enseignant',true,1)
        ON CONFLICT DO NOTHING;
        teacherid:=md5('YEM-DEMO-2026:course-teacher:'||courseid::text||':'||assignmentid::text)::uuid;
        INSERT INTO public.institutions_courseinstructor
          (id,school_id,course_id,staff_assignment_id,active,revision)
        VALUES(teacherid,sch,courseid,assignmentid,true,1)
        ON CONFLICT DO NOTHING;
        INSERT INTO public.institutions_courseunit
          (id,school_id,course_id,code,title,objectives,"order",active,revision)
        VALUES(md5('YEM-DEMO-2026:unit:'||courseid::text)::uuid,
          sch,courseid,'demo26-chapitre1',
          'Chapitre 1 - découverte et exercices (démo)',
          'Leçon fictive, exercices et évaluation de démonstration YEM.',1,true,1)
        ON CONFLICT DO NOTHING;
        slot_pos:=((class_pos-1)%5)+1;
        SELECT id INTO slotid FROM public.institutions_timetableslot
          WHERE school_id=sch AND year_id=yr AND code='demo26-c'||slot_pos LIMIT 1;
        INSERT INTO public.institutions_timetableentry
          (id,school_id,year_id,classroom_id,course_id,instructor_id,slot_id,room_id,
           weekday,effective_from,effective_to,active,revision,created_by_id,updated_at)
        SELECT
          md5('YEM-DEMO-2026:timetable:'||courseid::text)::uuid,
          sch,yr,cl.id,courseid,teacherid,slotid,NULL,
          (course_pos-1)%5,y.start_date,y.end_date,true,1,NULL,NOW()
        FROM public.institutions_academicyear y WHERE y.id=yr
        ON CONFLICT DO NOTHING;
        assessmentid:=md5('YEM-DEMO-2026:assessment:'||courseid::text)::uuid;
        INSERT INTO public.institutions_assessment
          (id,school_id,course_id,period_id,name,kind,assessment_date,weight,
           policy_snapshot,policy_layers,active,published,revision,created_at)
        SELECT assessmentid,sch,courseid,periodid,'Devoir n° 1 - simulation YEM','devoir',
          GREATEST(y.start_date,DATE '2026-10-20'),1,
          grading,'[]'::jsonb,true,true,1,NOW()
        FROM public.institutions_academicyear y WHERE y.id=yr
        ON CONFLICT DO NOTHING;
        FOR en IN SELECT e.id,st.student_code FROM public.institutions_enrollment e
           JOIN public.institutions_student st ON st.id=e.student_id
           WHERE e.school_id=sch AND e.year_id=yr AND e.classroom_id=cl.id AND e.active
             AND st.student_code LIKE 'DEMO26-'||s.tag||'-%'
        LOOP
          student_idx:=right(en.student_code,3)::int;
          grade_score:=8+((student_idx*3+course_pos*2+s.n)%11);
          grade_percent:=grade_score*5;
          grade_label:=CASE WHEN grade_percent>=85 THEN 'Très bien'
            WHEN grade_percent>=70 THEN 'Bien' WHEN grade_percent>=60 THEN 'Assez bien'
            WHEN grade_percent>=50 THEN 'Passable' ELSE 'Insuffisant' END;
          gradeid:=md5('YEM-DEMO-2026:grade:'||assessmentid::text||':'||en.id::text)::uuid;
          INSERT INTO public.institutions_assessmentgrade
            (id,school_id,assessment_id,enrollment_id,score,feedback,status,
             percent,label,revision,author_id,updated_at)
          VALUES(gradeid,sch,assessmentid,en.id,to_jsonb(grade_score),
            CASE WHEN grade_score>=14 THEN 'Travail sérieux (démo)'
                 ELSE 'Efforts à poursuivre (démo)' END,
            'calculated',grade_percent,grade_label,1,NULL,NOW())
          ON CONFLICT DO NOTHING;
        END LOOP;
      END LOOP;
      IF EXISTS(SELECT 1 FROM public.institutions_enrollment e
            JOIN public.institutions_student st ON st.id=e.student_id
            WHERE e.classroom_id=cl.id AND st.student_code LIKE 'DEMO26-'||s.tag||'-%')
      THEN
        sessionid:=md5('YEM-DEMO-2026:session:'||cl.id::text)::uuid;
        INSERT INTO public.institutions_attendancesession
          (id,school_id,classroom_id,attendance_date,slot,label,revision,
           closed_at,created_at,created_by_id,closed_by_id)
        VALUES(sessionid,sch,cl.id,DATE '2026-11-06','demo26-matin',
          'Appel du matin (démonstration)',1,NOW(),NOW(),NULL,NULL)
        ON CONFLICT DO NOTHING;
        FOR en IN SELECT e.id,st.student_code FROM public.institutions_enrollment e
            JOIN public.institutions_student st ON st.id=e.student_id
            WHERE e.school_id=sch AND e.classroom_id=cl.id AND e.active
              AND st.student_code LIKE 'DEMO26-'||s.tag||'-%'
        LOOP
          student_idx:=right(en.student_code,3)::int;
          INSERT INTO public.institutions_attendancemark
           (id,school_id,session_id,enrollment_id,status_code,status_label,
            status_group,note,justification,justified,revision,updated_by_id,updated_at)
          VALUES(md5('YEM-DEMO-2026:mark:'||sessionid::text||':'||en.id::text)::uuid,
            sch,sessionid,en.id,
            CASE WHEN student_idx%5=0 THEN 'a' WHEN student_idx%4=0 THEN 'r' ELSE 'p' END,
            CASE WHEN student_idx%5=0 THEN 'Absent' WHEN student_idx%4=0 THEN 'En retard' ELSE 'Présent' END,
            CASE WHEN student_idx%5=0 THEN 'absent' WHEN student_idx%4=0 THEN 'late' ELSE 'present' END,
            CASE WHEN student_idx%5=0 THEN 'Absence fictive pour test' ELSE '' END,
            '',false,1,NULL,NOW())
          ON CONFLICT DO NOTHING;
        END LOOP;
      END IF;
    END LOOP;
    -- Reports use the exact JSON shape expected by YEM's report PDF renderer.
    -- They are explicitly stamped DEMONSTRATION and non-official.
    FOR en IN
      SELECT e.id,e.year_id,e.student_id,e.classroom_id,st.first_name,
        st.last_name,st.student_code,st.identity_id,c.name AS class_name
      FROM public.institutions_enrollment e
      JOIN public.institutions_student st ON st.id=e.student_id
      JOIN public.institutions_academicclass c ON c.id=e.classroom_id
      WHERE e.school_id=sch AND e.year_id=yr AND e.active
        AND st.student_code LIKE 'DEMO26-'||s.tag||'-%'
      ORDER BY st.student_code
    LOOP
      SELECT jsonb_agg(jsonb_build_object(
        'course',co.id::text,'subject',sub.name,'coefficient',co.coefficient::text,
        'result',jsonb_build_object('status','calculated',
           'percent',ROUND(g.percent,2)::text,
           'score',ROUND(g.percent/5,2)::text,'label',g.label),
        'assessments',1
      ) ORDER BY sub.name),
      jsonb_agg(jsonb_build_object('assessment',a.id::text,
        'revision',a.revision,'grade',g.id::text,'grade_revision',g.revision)
        ORDER BY sub.name),
      ROUND(AVG(g.percent)/5,2),COUNT(*)::int
      INTO subject_rows,source_rows,overall_score,totalgrades
      FROM public.institutions_courseoffering co
      JOIN public.institutions_subject sub ON sub.id=co.subject_id
      JOIN public.institutions_assessment a ON a.course_id=co.id AND a.published
      JOIN public.institutions_assessmentgrade g ON g.assessment_id=a.id AND g.enrollment_id=en.id
      WHERE co.school_id=sch AND co.year_id=yr AND co.classroom_id=en.classroom_id
        AND sub.code LIKE 'demo26-%';
      IF totalgrades<1 THEN RAISE EXCEPTION 'Missing demo grades for %',en.student_code; END IF;
      grade_label:=CASE WHEN overall_score>=17 THEN 'Très bien'
        WHEN overall_score>=14 THEN 'Bien' WHEN overall_score>=12 THEN 'Assez bien'
        WHEN overall_score>=10 THEN 'Passable' ELSE 'Insuffisant' END;
      doc:=jsonb_build_object(
        'created_at',NOW()::text,
        'school',jsonb_build_object('id',sch::text,'name',school_name,'short_name',school_short_label),
        'student',jsonb_build_object('id',en.student_id::text,
          'code',en.student_code,'matricule_yem','YEM-'||upper(replace(en.identity_id::text,'-','')),
          'first_name',en.first_name,'last_name',en.last_name),
        'class',jsonb_build_object('id',en.classroom_id::text,'name',en.class_name),
        'year',jsonb_build_object('id',yr::text,'name',
            (SELECT name FROM public.institutions_academicyear WHERE id=yr)),
        'period',jsonb_build_object('id',periodid::text,'name','Trimestre 1 (démonstration)'),
        'subjects',subject_rows,
        'overall',jsonb_build_object('status','calculated',
          'percent',(overall_score*5)::text,'score',overall_score::text,'label',grade_label),
        'policy_snapshot',grading,
        'template',jsonb_build_object('title','BULLETIN FICTIF - DEMONSTRATION YEM - NON OFFICIEL',
          'precision',2,'show_score',true,'show_label',true,'show_rank',false,'missing_entry','exclude'),
        'layers','[]'::jsonb,'sources',source_rows,'recorded_grade_count',totalgrades,
        'demonstration_only',true
      );
      student_idx:=right(en.student_code,3)::int;
      INSERT INTO public.institutions_schoolreport
        (id,school_id,enrollment_id,year_id,period_id,period_key,status,snapshot,
         revision,created_at,published_at,prepared_by_id)
      VALUES(md5('YEM-DEMO-2026:report:'||en.id::text)::uuid,
        sch,en.id,yr,periodid,periodid::text,
        CASE WHEN student_idx<=5 THEN 'published' ELSE 'draft' END,
        doc,1,NOW(),CASE WHEN student_idx<=5 THEN NOW() ELSE NULL END,NULL)
      ON CONFLICT DO NOTHING;
    END LOOP;
  END LOOP;
END
$demo$;
