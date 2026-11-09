-- One-off correction limited to the 45 fully fictitious YEM demo records.
-- Safe to run repeatedly: only mismatched dummy birthdays change.
WITH corrected AS (
 SELECT st.id AS student_id,
   (CASE
     WHEN cl.code ~ 'petite_section' THEN DATE '2022-06-15'
     WHEN cl.code ~ 'moyenne_section' THEN DATE '2021-06-15'
     WHEN cl.code ~ 'grande_section' THEN DATE '2020-06-15'
     WHEN cl.code ~ '1re-annee' THEN DATE '2019-06-15'
     WHEN cl.code ~ '2e-annee' THEN DATE '2018-06-15'
     WHEN cl.code ~ '3e-annee-a' THEN DATE '2017-06-15'
     WHEN cl.code ~ '3e-annee-b' THEN DATE '2016-06-15'
     WHEN cl.code ~ '4e-annee' THEN DATE '2015-06-15'
     WHEN cl.code ~ '5e-annee' THEN DATE '2014-06-15'
     WHEN cl.code ~ 'cp1' THEN DATE '2019-06-15'
     WHEN cl.code ~ 'cp2' THEN DATE '2018-06-15'
     WHEN cl.code ~ 'ce1' THEN DATE '2017-06-15'
     WHEN cl.code ~ 'ce2' THEN DATE '2016-06-15'
     WHEN cl.code ~ 'cm1' THEN DATE '2015-06-15'
     WHEN cl.code ~ 'cm2' THEN DATE '2014-06-15'
     WHEN cl.code ~ 'sixieme|demo-6a' THEN DATE '2014-06-15'
     WHEN cl.code ~ 'cinquieme|demo-5a' THEN DATE '2013-06-15'
     WHEN cl.code ~ 'quatrieme|demo-4a' THEN DATE '2012-06-15'
     WHEN cl.code ~ 'troisieme|demo-3a' THEN DATE '2011-06-15'
     WHEN cl.code ~ 'seconde|demo-2nde' THEN DATE '2010-06-15'
     WHEN cl.code ~ 'premiere' THEN DATE '2009-06-15'
     WHEN cl.code ~ 'terminale' THEN DATE '2008-06-15'
     ELSE DATE '2012-06-15' END
     + ((right(st.student_code,3)::integer*11)%25)
   ) AS proper_date
 FROM institutions_student st
 JOIN institutions_enrollment en ON en.student_id=st.id
 JOIN institutions_academicclass cl ON cl.id=en.classroom_id
 WHERE st.student_code LIKE 'DEMO26-%'
   AND st.extra_fields->>'jeu'='YEM-2026-11-09'
   AND st.extra_fields->>'demo'='true'
   AND en.school_id=st.school_id
   AND cl.school_id=st.school_id
   AND cl.year_id=en.year_id
   AND st.school_id IN (
     '96f99506-a8d6-4dab-b292-4076800c9bd7',
     'b8ccefc7-c993-49f3-b2f3-70e59ca7db20',
     'eae64fe7-bac2-4b94-a999-4f278a33ef2a'
   )
)
UPDATE institutions_student st
SET date_of_birth=corrected.proper_date,
    revision=st.revision+1
FROM corrected
WHERE st.id=corrected.student_id
  AND st.date_of_birth IS DISTINCT FROM corrected.proper_date
RETURNING st.student_code,st.date_of_birth;