import fs from 'node:fs';
import sharp from 'sharp';
const root='docs/diagrams/';
const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;');
function diagram(name,w,h,nodes,edges){
 let svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#243b53"/></marker></defs><rect width="100%" height="100%" fill="white"/>`;
 for(const e of edges){svg+=`<path d="${e.path}" stroke="#526879" stroke-width="2" fill="none" ${e.label==='extend'?'stroke-dasharray="7,5"':''} ${e.arrow?'marker-end="url(#arrow)"':''}/><text x="${e.x}" y="${e.y}" font-family="Arial" font-size="16" fill="#243b53">${escape(e.label)}</text>`;}
 for(const n of nodes){if(n.actor){const cx=n.x+n.w/2,cy=n.y+8;svg+=`<circle cx="${cx}" cy="${cy}" r="14" fill="white" stroke="#243b53" stroke-width="2"/><path d="M${cx} ${cy+14} v35 m-30 -22 h60 m-30 22 l-24 23 m24 -23 l24 23" fill="none" stroke="#243b53" stroke-width="2"/><text x="${n.x+12}" y="${cy+91}" font-family="Arial" font-size="20">${n.lines[0]}</text>`;continue;}svg+=`<rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="${n.round?90:0}" fill="white" stroke="#243b53" stroke-width="2"/>`;
 n.lines.forEach((line,i)=>{svg+=`<text x="${n.round?n.x+n.w/2:n.x+14}" text-anchor="${n.round?'middle':'start'}" y="${n.y+(n.round?39:29)+i*23}" font-family="Arial" font-size="${i?16:19}" font-weight="${i?'normal':'bold'}" fill="#172c40">${escape(line)}</text>`;});}
 if(name==='use-case')svg+=`<rect x="380" y="1" width="880" height="860" fill="none" stroke="#687887"/><text x="420" y="850" font-family="Arial" font-size="16">ИС учета успеваемости; вход — предусловие всех сценариев</text>`;svg+='</svg>';fs.writeFileSync(root+name+'.svg',svg);return sharp(Buffer.from(svg)).png().toFile(root+name+'.png');
}
await diagram('er-diagram',1250,1050,[
{x:30,y:20,w:290,h:135,lines:['teachers / Преподаватели','PK id; ФИО; кафедра','должность; степень; контакты']},
{x:450,y:20,w:300,h:155,lines:['groups / Группы','PK id; FK curator_id','название; специальность; курс','форма; год набора']},
{x:910,y:20,w:310,h:155,lines:['students / Студенты','PK id; FK group_id','ФИО; рождение; пол; контакты','финансирование; статус; прием']},
{x:30,y:350,w:290,h:155,lines:['disciplines / Дисциплины','PK id; название; описание','лекции; практики; лабораторные','форма контроля']},
{x:450,y:350,w:300,h:155,lines:['assignments / Назначения','PK id; FK group_id','FK discipline_id; FK teacher_id','семестр; учебный год']},
{x:910,y:350,w:310,h:155,lines:['users / Пользователи','PK id; UNIQUE username','FK student_id / teacher_id','хеш пароля; роль; активность']},
{x:450,y:665,w:300,h:155,lines:['assessments / Работы','PK id; FK assignment_id','название; вид; вес; шкала']},
{x:910,y:665,w:310,h:155,lines:['grades / Оценки','PK id; FK student_id','FK assessment_id; значение','комментарий']},
{x:30,y:665,w:290,h:145,lines:['sessions / Сессии','PK token_hash; FK user_id','срок действия']},
{x:30,y:900,w:460,h:120,lines:['audit_log / Журнал действий','PK id; FK user_id; действие; сущность','ID объекта; дата и время']},
{x:670,y:900,w:550,h:120,lines:['login_attempts / Попытки входа','хеш ключа; время попытки','Техническая таблица ограничения частоты']}
],[
{path:'M320 70 H450',x:345,y:60,label:'1 : M'},
{path:'M750 70 H910',x:795,y:60,label:'1 : M'},
{path:'M600 175 V350',x:610,y:255,label:'1 : M'},
{path:'M175 155 V285 H500 V350',x:270,y:278,label:'1 : M'},
{path:'M320 425 H450',x:345,y:415,label:'1 : M'},
{path:'M600 505 V665',x:610,y:590,label:'1 : M'},
{path:'M750 740 H910',x:798,y:730,label:'1 : M'},
{path:'M1200 175 H1240 V740 H1220',x:1160,y:620,label:'1 : M'},
{path:'M1060 175 V350',x:1070,y:265,label:'1 : 0..1'},
{path:'M300 155 V205 H880 V395 H910',x:640,y:198,label:'1 : 0..1'},
{path:'M910 470 H820 V610 H175 V665',x:280,y:600,label:'Пользователь 1 : M сессий'},
{path:'M1060 505 V860 H260 V900',x:520,y:851,label:'Пользователь 1 : M событий'}
]);
await diagram('use-case',1280,880,[
{x:30,y:65,w:230,h:80,actor:true,lines:['Администратор']},
{x:30,y:285,w:230,h:80,actor:true,lines:['Деканат']},
{x:30,y:505,w:230,h:80,actor:true,lines:['Преподаватель']},
{x:30,y:725,w:230,h:80,actor:true,lines:['Студент']},
{x:400,y:25,w:370,h:90,round:true,lines:['Управление пользователями','Роли и активность']},
{x:870,y:25,w:365,h:90,round:true,lines:['Архив и журнал действий']},
{x:400,y:235,w:370,h:110,round:true,lines:['Ведение справочников','Студенты, группы, дисциплины','и преподаватели']},
{x:870,y:235,w:365,h:110,round:true,lines:['Планирование семестра','Назначение дисциплин','и преподавателей']},
{x:400,y:465,w:370,h:110,round:true,lines:['Работы и оценки','Собственные назначения','Расчет взвешенного итога']},
{x:870,y:465,w:365,h:110,round:true,lines:['Формирование отчетов','Ведомости, рейтинг, должники','Статистика, качество знаний']},
{x:400,y:705,w:370,h:110,round:true,lines:['Просмотр своих результатов','Оценки, сводная ведомость','и личное место в рейтинге']},
{x:870,y:705,w:365,h:110,round:true,lines:['Экспорт и печать','Excel и PDF','С учетом прав пользователя']}
],[
{path:'M175 105 H340 V70 H400',x:270,y:60,label:''},{path:'M340 70 V15 H1050 V25',x:700,y:16,label:''},
{path:'M340 105 V290 H400',x:272,y:200,label:'полный доступ'},
{path:'M175 325 H350 V290 H400',x:265,y:300,label:''},
{path:'M350 325 V380 H1030 V345',x:675,y:375,label:''},
{path:'M350 325 V420 H1050 V465',x:390,y:413,label:''},
{path:'M175 545 H400',x:270,y:533,label:''},{path:'M300 545 V610 H1050 V575',x:355,y:602,label:'ведомость своей дисциплины'},
{path:'M175 765 H400',x:275,y:755,label:''},
{path:'M870 760 H770',x:779,y:741,label:'extend',arrow:true},
{path:'M1060 705 V575',x:1070,y:653,label:'extend',arrow:true},
{path:'M340 290 V640 H850 V535 H870',x:420,y:635,label:'Администратор: все отчеты и оценки'}
]);
await diagram('architecture',1200,440,[
{x:25,y:150,w:330,h:130,lines:['Браузер','HTML + CSS + JavaScript','Русскоязычный интерфейс']},
{x:440,y:110,w:330,h:210,lines:['Контейнер web','FastAPI → сервисы → SQL','Dishka: пул и соединение','Сессии и проверка ролей','Excel / PDF']},
{x:855,y:150,w:320,h:130,lines:['Контейнер db','PostgreSQL 17','Том pgdata; SQL DDL / DML']}
],[{path:'M355 200 H440',x:367,y:187,label:'HTTP',arrow:true},{path:'M770 200 H855',x:790,y:187,label:'SQL',arrow:true}]);
