import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cfb_drive_counts import regulation_drive_counts

def test_exclusions_and_ownership():
 def row(i,**kw):return dict(game_id='g',drive_id=str(i),team_id='A',start_period='1',end_period='1',offensive_plays='3',**kw)
 rows=[row(1),row(2),dict(row(3),team_id='B'),dict(row(4),start_period='5',end_period='5'),dict(row(5),offensive_plays='0'),dict(row(6),start_period='')]
 c,e=regulation_drive_counts(rows)
 assert c[('g','A')]==2 and c[('g','B')]==1
 assert e=={'non_regulation':1,'no_offensive_plays':1,'invalid_fields':1}

def test_duplicate_rejected():
 r=dict(game_id='g',drive_id='1',team_id='A',start_period='1',end_period='1',offensive_plays='3')
 try:regulation_drive_counts([r,r])
 except ValueError:return
 raise AssertionError('Duplicate silently counted')

if __name__=='__main__':test_exclusions_and_ownership();test_duplicate_rejected();print('Drive-count tests passed')
