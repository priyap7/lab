import os, tempfile
from fastapi.testclient import TestClient

# Tests use a temporary SQLite file so they never alter a real user's database.
tmp = tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False); tmp.close()
os.environ['DATABASE_PATH'] = tmp.name
from main import app
client = TestClient(app)

def test_health_and_database():
    r=client.get('/api/health'); assert r.status_code==200 and r.json()['database']=='sqlite'
    assert client.get('/api/foods').status_code==200

def test_meal_persistence_crud():
    body={'name':'Test meal','meal_type':'Lunch','portion_g':150,'calories':195,'protein':4,'carbs':42,'fat':1,'fibre':2,'notes':'test'}
    r=client.post('/api/meals',json=body); assert r.status_code==201, r.text
    mid=r.json()['id']; assert any(x['id']==mid for x in client.get('/api/meals').json())
    body['name']='Updated test meal'; assert client.put(f'/api/meals/{mid}',json=body).status_code==200
    assert client.delete(f'/api/meals/{mid}').status_code==200
    assert all(x['id']!=mid for x in client.get('/api/meals').json())

def test_goals_validation_and_persistence():
    g={'calories':2100,'protein':120,'carbs':260,'fat':65,'fibre':32}
    assert client.put('/api/goals',json=g).status_code==200
    assert client.get('/api/goals').json()['calories']==2100
    assert client.put('/api/goals',json={**g,'calories':-1}).status_code==422

def test_bad_upload_type_rejected():
    r=client.post('/api/analyze',files={'image':('not-image.txt',b'hello','text/plain')})
    assert r.status_code==415

def test_invalid_meal_rejected():
    r=client.post('/api/meals',json={'name':'bad','meal_type':'Lunch','portion_g':0,'calories':-1,'protein':0,'carbs':0,'fat':0,'fibre':0})
    assert r.status_code==422
