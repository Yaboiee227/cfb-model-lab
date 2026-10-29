import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit',ROOT/'scripts/audit_projection_errors.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def test_home_spread_sign_and_paired_sample(tmp_path):
 p=tmp_path/'case.csv';p.write_text('gameId,week,awayTeam,homeTeam,awayScore,homeScore,modelSpreadHome,marketSpreadHome,modelTotal,marketTotal\na,1,A,H,20,27,-7,-3,47,45\nb,1,B,H,14,10,4,,24,\n')
 # ROOT is replaced only to allow an isolated synthetic fixture.
 original=m.R;m.R=tmp_path
 try:r=m.audit(p,'test')
 finally:m.R=original
 spread,total=r['groups'];assert spread['modelMAE']==0;assert spread['marketMAE']==4;assert spread['pairedMAEDelta']==-4
 assert spread['games']==1 and spread['excludedMissingReference']==['b'];assert total['modelMAE']==0 and total['marketMAE']==2
