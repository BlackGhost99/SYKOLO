-- YEM: synthetic demonstration records only. Idempotent, insert-only.
-- Restrict to the three existing schools. Never deletes or updates real profiles.
DO $demo$
DECLARE
  s record; x record; idx integer; sch uuid; yr uuid; cy uuid; lvl uuid; cls uuid;
  sid uuid; ident uuid; gid uuid; ev uuid; count_classes integer;
  start_on date; end_on date; cls_code text;
  school_data jsonb := '[
    {"id":"96f99506-a8d6-4dab-b292-4076800c9bd7","tag":"CES8","kind":"complexe","n":1},
    {"id":"b8ccefc7-c993-49f3-b2f3-70e59ca7db20","tag":"LP1","kind":"lycee","n":2},
    {"id":"eae64fe7-bac2-4b94-a999-4f278a33ef2a","tag":"LP2","kind":"lycee","n":3}
  ]'::jsonb;
  complex_levels jsonb := '[
    {"cycle":"prescolaire","cycle_name":"Maternelle","code":"petite_section","name":"Petite Section","sort":1},
    {"cycle":"prescolaire","cycle_name":"Maternelle","code":"moyenne_section","name":"Moyenne Section","sort":2},
    {"cycle":"prescolaire","cycle_name":"Maternelle","code":"grande_section","name":"Grande Section","sort":3},
    {"cycle":"primaire","cycle_name":"Primaire","code":"cp1","name":"CP1","sort":1},
    {"cycle":"primaire","cycle_name":"Primaire","code":"cp2","name":"CP2","sort":2},
    {"cycle":"primaire","cycle_name":"Primaire","code":"ce1","name":"CE1","sort":3},
    {"cycle":"primaire","cycle_name":"Primaire","code":"ce2","name":"CE2","sort":4},
    {"cycle":"primaire","cycle_name":"Primaire","code":"cm1","name":"CM1","sort":5},
    {"cycle":"primaire","cycle_name":"Primaire","code":"cm2","name":"CM2","sort":6}
  ]'::jsonb;
  lycee_levels jsonb := '[
    {"cycle":"college","cycle_name":"Collège","code":"sixieme","name":"Sixième","sort":1},
    {"cycle":"college","cycle_name":"Collège","code":"cinquieme","name":"Cinquième","sort":2},
    {"cycle":"college","cycle_name":"Collège","code":"quatrieme","name":"Quatrième","sort":3},
    {"cycle":"college","cycle_name":"Collège","code":"troisieme","name":"Troisième","sort":4},
    {"cycle":"lycee_general","cycle_name":"Lycée général","code":"seconde","name":"Seconde","sort":5},
    {"cycle":"lycee_general","cycle_name":"Lycée général","code":"premiere","name":"Première","sort":6},
    {"cycle":"lycee_general","cycle_name":"Lycée général","code":"terminale","name":"Terminale","sort":7}
  ]'::jsonb;
  firstname text[] := ARRAY['Lina','Noé','Amina','Malik','Léa','Yanis','Maya','Eden','Inès','Samuel','Célia','Nolan','Naïla','Mathis','Élise'];
  lastname text[] := ARRAY['MBOUMBA','ONDO','NZÉ','MENGUE','MOUSSAVOU','OBAME','NKOGHE','ESSONO','BANGUÉ','NDOUNG','MBADINGA','NGUEMA','EKOGHA','NDONG','MOUKALA'];
  parentname text[] := ARRAY['Chantal','Jean-Claude','Brigitte','Emmanuel','Rosine','Patrick','Ariane','Christian','Isabelle','François','Cécile','Daniel','Marina','Gabriel','Sylvie'];
  job text[] := ARRAY['Enseignante de français','Professeur de mathématiques','Professeur d’anglais','Professeur de sciences','Professeur d’histoire-géographie','Éducatrice / professeur polyvalent'];
BEGIN
  PERFORM pg_advisory_xact_lock(20261109);
  FOR s IN SELECT * FROM jsonb_to_recordset(school_data)
      AS z(id uuid,tag text,kind text,n int)
  LOOP
    sch:=s.id;
    IF NOT EXISTS(SELECT 1 FROM public.institutions_school WHERE id=sch) THEN
      RAISE EXCEPTION 'Missing targeted school: %',sch;
    END IF;
    SELECT id,start_date,end_date INTO yr,start_on,end_on
      FROM public.institutions_academicyear
     WHERE school_id=sch AND code='2026-2027' LIMIT 1;
    IF yr IS NULL THEN
      yr:=md5('YEM-DEMO-2026:year:'||s.tag)::uuid;
      start_on:=DATE '2026-09-01'; end_on:=DATE '2027-07-31';
      INSERT INTO public.institutions_academicyear
        (id,school_id,code,name,start_date,end_date,active,revision,status)
      VALUES(yr,sch,'2026-2027','Année scolaire 2026-2027',start_on,end_on,true,1,'current')
      ON CONFLICT DO NOTHING;
      SELECT id,start_date,end_date INTO yr,start_on,end_on
        FROM public.institutions_academicyear WHERE school_id=sch AND code='2026-2027';
    END IF;
    -- One actual first-trimester period; no synthetic year-end decision.
    INSERT INTO public.institutions_academicperiod
      (id,school_id,year_id,code,name,start_date,end_date,"order",active,revision)
    VALUES(md5('YEM-DEMO-2026:period:'||s.tag)::uuid,sch,yr,
      'demo26-trim1','Trimestre 1 (démonstration)',start_on,
      LEAST(end_on,DATE '2026-12-18'),1,true,1)
    ON CONFLICT DO NOTHING;
    FOR x IN SELECT * FROM jsonb_to_recordset(
      CASE WHEN s.kind='complexe' THEN complex_levels ELSE lycee_levels END
    ) AS z(cycle text,cycle_name text,code text,name text,sort int)
    LOOP
      cy:=md5('YEM-DEMO-2026:cycle:'||s.tag||':'||x.cycle)::uuid;
      INSERT INTO public.institutions_academiccycle
       (id,school_id,code,name,"order",active,revision)
      VALUES(cy,sch,x.cycle,x.cycle_name,
       CASE WHEN x.cycle='prescolaire' THEN 1 WHEN x.cycle='primaire' THEN 2
            WHEN x.cycle='college' THEN 3 ELSE 4 END,true,1)
      ON CONFLICT DO NOTHING;
      -- Look up the school-scoped cycle in case it already existed before seeding.
      SELECT id INTO cy FROM public.institutions_academiccycle
       WHERE school_id=sch AND code=x.cycle LIMIT 1;
      lvl:=md5('YEM-DEMO-2026:level:'||s.tag||':'||x.code)::uuid;
      INSERT INTO public.institutions_academiclevel
        (id,school_id,cycle_id,code,name,"order",active,revision)
      VALUES(lvl,sch,cy,x.code,x.name,x.sort,true,1)
      ON CONFLICT DO NOTHING;
      SELECT id INTO lvl FROM public.institutions_academiclevel
        WHERE school_id=sch AND cycle_id=cy AND code=x.code LIMIT 1;
      INSERT INTO public.institutions_academicclass
        (id,school_id,year_id,level_id,track_id,code,name,capacity,active,revision)
      VALUES(md5('YEM-DEMO-2026:class:'||s.tag||':'||x.code)::uuid,
        sch,yr,lvl,NULL,'demo26-'||x.code||'-a',x.name||' A (démo)',30,true,1)
      ON CONFLICT DO NOTHING;
    END LOOP;
    -- All fictitious personnel have no access to the login system.
    FOR idx IN 1..6 LOOP
      INSERT INTO public.institutions_staffrecord
        (id,school_id,account_id,staff_code,first_name,last_name,position,hired_on,active,revision,created_at)
      VALUES(md5('YEM-DEMO-2026:staff:'||s.tag||':'||idx)::uuid,
        sch,NULL,'demo26-'||lower(s.tag)||'-'||lpad(idx::text,2,'0'),
        parentname[idx],lastname[16-idx],job[idx],DATE '2026-08-24',true,1,NOW())
      ON CONFLICT DO NOTHING;
    END LOOP;
    FOR x IN SELECT * FROM jsonb_to_recordset('[
      {"code":"francais","name":"Français"},
      {"code":"maths","name":"Mathématiques"},
      {"code":"anglais","name":"Anglais"},
      {"code":"histoire_geo","name":"Histoire-géographie"},
      {"code":"svt","name":"Sciences de la vie et de la Terre"},
      {"code":"eps","name":"Éducation physique et sportive"},
      {"code":"lecture","name":"Lecture"},
      {"code":"ecriture","name":"Écriture / graphisme"},
      {"code":"eveil","name":"Éveil scientifique"},
      {"code":"langage","name":"Langage et expression"}
    ]'::jsonb) AS z(code text,name text)
    LOOP
      INSERT INTO public.institutions_subject
        (id,school_id,code,name,description,active,revision)
      VALUES(md5('YEM-DEMO-2026:subject:'||s.tag||':'||x.code)::uuid,
        sch,'demo26-'||x.code,x.name,'Matière fictive pour les essais YEM',true,1)
      ON CONFLICT DO NOTHING;
    END LOOP;
    FOR idx IN 1..5 LOOP
      INSERT INTO public.institutions_timetableslot
       (id,school_id,year_id,code,label,start_time,end_time,active,revision)
      VALUES(md5('YEM-DEMO-2026:slot:'||s.tag||':'||idx)::uuid,
        sch,yr,'demo26-c'||idx,'Créneau '||idx||' (démo)',
        (ARRAY['08:00','09:00','10:15','11:15','14:00'])[idx]::time,
        (ARRAY['09:00','10:00','11:15','12:15','15:00'])[idx]::time,true,1)
      ON CONFLICT DO NOTHING;
    END LOOP;
    -- A real-looking but non-contactable guardian for each fictitious child.
    SELECT COUNT(*) INTO count_classes FROM public.institutions_academicclass
      WHERE school_id=sch AND year_id=yr AND active
        AND code LIKE 'demo26-%';
    IF count_classes<7 THEN RAISE EXCEPTION 'Missing demonstration classes in %',s.tag; END IF;
    FOR idx IN 1..15 LOOP
      SELECT id,code INTO cls,cls_code FROM public.institutions_academicclass
       WHERE school_id=sch AND year_id=yr AND active
         AND code LIKE 'demo26-%'
       ORDER BY code, id LIMIT 1 OFFSET ((idx-1)%count_classes);
      ident:=md5('YEM-DEMO-2026:identity:'||s.tag||':'||idx)::uuid;
      sid:=md5('YEM-DEMO-2026:student:'||s.tag||':'||idx)::uuid;
      INSERT INTO public.institutions_studentidentity (id) VALUES(ident)
        ON CONFLICT DO NOTHING;
      INSERT INTO public.institutions_student
       (id,school_id,identity_id,student_code,first_name,last_name,
        date_of_birth,admission_date,gender,place_of_birth,nationality,
        address,previous_school,extra_fields,documents,active,revision,created_at)
      VALUES(sid,sch,ident,'DEMO26-'||s.tag||'-'||lpad(idx::text,3,'0'),
        firstname[idx],lastname[idx],
        (CASE
          WHEN cls_code ~ 'petite_section' THEN DATE '2022-06-15'
          WHEN cls_code ~ 'moyenne_section' THEN DATE '2021-06-15'
          WHEN cls_code ~ 'grande_section' THEN DATE '2020-06-15'
          WHEN cls_code ~ 'cp1' THEN DATE '2019-06-15'
          WHEN cls_code ~ 'cp2' THEN DATE '2018-06-15'
          WHEN cls_code ~ 'ce1' THEN DATE '2017-06-15'
          WHEN cls_code ~ 'ce2' THEN DATE '2016-06-15'
          WHEN cls_code ~ 'cm1' THEN DATE '2015-06-15'
          WHEN cls_code ~ 'cm2' THEN DATE '2014-06-15'
          WHEN cls_code ~ 'sixieme|demo-6a' THEN DATE '2014-06-15'
          WHEN cls_code ~ 'cinquieme|demo-5a' THEN DATE '2013-06-15'
          WHEN cls_code ~ 'quatrieme|demo-4a' THEN DATE '2012-06-15'
          WHEN cls_code ~ 'troisieme|demo-3a' THEN DATE '2011-06-15'
          WHEN cls_code ~ 'seconde|demo-2nde' THEN DATE '2010-06-15'
          WHEN cls_code ~ 'premiere' THEN DATE '2009-06-15'
          WHEN cls_code ~ 'terminale' THEN DATE '2008-06-15'
          ELSE DATE '2012-06-15' END + ((idx*11)%25)),
        DATE '2026-09-15',CASE WHEN idx%2=0 THEN 'M' ELSE 'F' END,
        'Libreville','Gabonaise','Quartier témoin '||idx||', Libreville',
        'Établissement fictif (démo)',
        jsonb_build_object('demo',true,'jeu','YEM-2026-11-09','identite','FICTIVE'),
        '{"acte_naissance":true,"photo":false}'::jsonb,true,1,NOW())
      ON CONFLICT DO NOTHING;
      ev:=md5('YEM-DEMO-2026:enrollment:'||s.tag||':'||idx)::uuid;
      INSERT INTO public.institutions_enrollment
        (id,school_id,student_id,year_id,classroom_id,enrolled_on,status,active,revision,created_at)
      VALUES(ev,sch,sid,yr,cls,GREATEST(start_on,DATE '2026-09-15'),'inscrit',true,1,NOW())
      ON CONFLICT DO NOTHING;
      gid:=md5('YEM-DEMO-2026:guardian:'||s.tag||':'||idx)::uuid;
      INSERT INTO public.institutions_studentguardian
        (id,school_id,student_id,full_name,relationship,phone,email,
        profession,address,is_primary,active,revision)
      VALUES(gid,sch,sid,parentname[idx]||' '||lastname[idx],
        CASE WHEN idx%3=0 THEN 'Tuteur' WHEN idx%2=0 THEN 'Père' ELSE 'Mère' END,
        '000-'||s.n||'-'||lpad(idx::text,4,'0'),
        'demo.'||lower(s.tag)||'.parent'||idx||'@example.invalid',
        (ARRAY['Commerçant(e)','Employé(e)','Entrepreneur(e)','Fonctionnaire','Artisan(e)'])[((idx-1)%5)+1],
        'Libreville · Adresse fictive '||idx,true,true,1)
      ON CONFLICT DO NOTHING;
      IF idx%4=0 THEN
        INSERT INTO public.institutions_studentguardian
          (id,school_id,student_id,full_name,relationship,phone,email,profession,address,is_primary,active,revision)
        VALUES(md5('YEM-DEMO-2026:guardian2:'||s.tag||':'||idx)::uuid,
          sch,sid,'Alex '||lastname[idx],'Second responsable',
          '000-'||s.n||'-'||lpad((idx+100)::text,4,'0'),
          'demo.'||lower(s.tag)||'.second'||idx||'@example.invalid',
          'Responsable fictif','Libreville · Adresse fictive '||idx,false,true,1)
        ON CONFLICT DO NOTHING;
      END IF;
    END LOOP;
  END LOOP;
END
$demo$;
