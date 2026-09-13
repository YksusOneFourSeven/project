-- Контроль количества и примеры SELECT, JOIN, GROUP BY, агрегатов.
SELECT 'students' AS entity,count(*) FROM students UNION ALL SELECT 'groups',count(*) FROM groups UNION ALL SELECT 'disciplines',count(*) FROM disciplines UNION ALL SELECT 'teachers',count(*) FROM teachers UNION ALL SELECT 'grades',count(*) FROM grades;
SELECT s.full_name,g.name FROM students s JOIN groups g ON g.id=s.group_id ORDER BY s.id;
SELECT group_id,round(avg(final_grade) FILTER(WHERE control_form<>'зачет'),2) AS average FROM results GROUP BY group_id;
SELECT * FROM results WHERE final_grade=2 AND control_form<>'зачет' OR final_grade=0 AND control_form='зачет';
