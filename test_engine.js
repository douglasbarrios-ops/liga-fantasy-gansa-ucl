// Extract the scoring engine from index.html and run it against data.json.
const fs = require('fs');
const html = fs.readFileSync('index.html','utf8');
const start = html.indexOf('const RULES = {');
const end = html.indexOf('/* ====', start);
eval(html.slice(start, end));
const data = JSON.parse(fs.readFileSync('data.json','utf8'));

const done = data.standings.length>=36 && data.standings.every(s=>(s.played||0)>=8);
const po = playoffWinners(data.matches);
console.log('league phase complete:', done);
console.log('playoff winners:', po.size, [...po].slice(0,4).join(', '), '...');

let grand=0; const rows=[];
for (const [mgr,teams] of Object.entries(data.draft)){
  const rs = teams.map(t=>scoreClub(t,data,po,done));
  const tot = rs.reduce((s,r)=>s+r.total,0); grand+=tot;
  rows.push([mgr,tot,rs]);
}
rows.sort((a,b)=>b[1]-a[1]);
for (const [mgr,tot,rs] of rows){
  console.log(`\n${mgr.padEnd(8)} ${String(tot).padStart(3)}`);
  for (const r of rs.sort((a,b)=>b.total-a.total))
    console.log(`   ${r.club.padEnd(20)} pos ${String(r.pos).padStart(2)}  liga ${String(r.league).padStart(2)}  bono +${r.bonus}  ko ${String(r.ko).padStart(2)}  = ${r.total}`);
}

// --- invariants -----------------------------------------------------------
const leagueMatches = data.matches.filter(m=>m.stage==='LEAGUE');
let expectedLeaguePts=0;
for (const m of leagueMatches) expectedLeaguePts += (m.homeScore===m.awayScore?2:3);
const actualLeague = rows.flatMap(r=>r[2]).reduce((s,r)=>s+r.league,0);
console.log('\n--- checks ---');
console.log('league pts distributed:', actualLeague, 'expected:', expectedLeaguePts, actualLeague===expectedLeaguePts?'OK':'FAIL');

const bonusTotal = rows.flatMap(r=>r[2]).reduce((s,r)=>s+r.bonus,0);
console.log('bonus pts:', bonusTotal, 'expected: 8*3 + 16*1 + 8*1 =', 8*3+16*1+8, bonusTotal===8*3+16+8?'OK':'FAIL');

const koM = data.matches.filter(m=>['R16','QF','SF','FINAL'].includes(m.stage));
let expKo=0; for (const m of koM) expKo += (m.homeScore===m.awayScore?2:3);
const actKo = rows.flatMap(r=>r[2]).reduce((s,r)=>s+r.ko,0);
console.log('knockout pts:', actKo, 'expected:', expKo, actKo===expKo?'OK':'FAIL');

const poM = data.matches.filter(m=>m.stage==='PLAYOFF');
console.log('playoff legs scored 0:', poM.every(m=>matchPoints(m,m.home)===0 && matchPoints(m,m.away)===0)?'OK':'FAIL');
console.log('grand total:', grand);
