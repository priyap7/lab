from __future__ import annotations
import base64, json, os, re, sqlite3, time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from PIL import Image, UnidentifiedImageError
from io import BytesIO

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.getenv('DATABASE_PATH', str(BASE_DIR / 'food_ai.sqlite3'))
MAX_IMAGE_BYTES = int(os.getenv('MAX_IMAGE_MB', '10')) * 1024 * 1024
ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp'}
app = FastAPI(title='Food AI Intelligence API', version='1.0.0', description='Uncertainty-aware food recognition and meal tracking API')
origins = [x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=['GET','POST','PUT','DELETE','OPTIONS'], allow_headers=['Content-Type','Authorization'])

# Small transparent starter reference table. This is NOT a bundled IFCT/USDA dataset.
# Production use should import properly licensed records and retain source IDs/versions.
SEED_FOODS = [
 ('apple','apple|raw apple|सेब',52,0.3,13.8,0.2,2.4,'USDA FoodData Central generic apple reference; verify record before production'),
 ('banana','banana|raw banana|केला',89,1.1,22.8,0.3,2.6,'USDA FoodData Central generic banana reference; verify record before production'),
 ('pomegranate','pomegranate|pomegranate arils|अनार',83,1.7,18.7,1.2,4.0,'USDA FoodData Central generic pomegranate reference; verify record before production'),
 ('cooked white rice','cooked white rice|white rice cooked|rice|चावल',130,2.7,28.2,0.3,0.4,'USDA FoodData Central generic cooked white rice reference; verify preparation and record'),
 ('roti','roti|chapati|phulka|रोटी|चपाती',297,9.8,55.0,7.5,8.0,'Starter generic roti estimate; recipe/flour/oil vary; not a verified IFCT record'),
 ('plain cooked dal','plain cooked dal|dal|lentil stew|दाल',116,7.6,20.1,0.4,7.9,'Generic cooked lentil reference; recipe/oil varies; confirm matching recipe'),
 ('paneer','paneer|पनीर',265,18.3,1.2,20.8,0.0,'Generic paneer estimate; moisture and fat vary; verify matching record'),
 ('plain yogurt','plain yogurt|curd|dahi|दही',61,3.5,4.7,3.3,0.0,'USDA FoodData Central generic plain yogurt reference; milk fat varies'),
 ('idli','idli|इडली',58,2.0,12.0,0.4,0.8,'Generic idli estimate; recipe and size vary; verify matching record'),
 ('dosa','dosa|डोसा',168,4.0,29.0,3.7,1.5,'Generic plain dosa estimate; oil and batter recipe vary'),
 ('pizza','pizza|cheese pizza',266,11.0,33.0,10.0,2.3,'USDA FoodData Central generic cheese pizza reference; toppings/crust vary'),
 ('salad','salad|vegetable salad|सलाद',35,1.5,7.0,0.4,2.5,'Generic no-dressing vegetable salad estimate; dressing changes values'),
 ('cooked potato','cooked potato|potato|आलू',87,1.9,20.1,0.1,1.8,'USDA FoodData Central generic cooked potato reference; cooking method varies'),
 ('cooked chicken breast','cooked chicken breast|chicken breast',165,31.0,0.0,3.6,0.0,'USDA FoodData Central generic cooked chicken breast reference; verify cooking method'),
]

def now_iso() -> str: return datetime.now(timezone.utc).isoformat()
@contextmanager
def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA foreign_keys=ON')
        yield con
        con.commit()
    finally: con.close()

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS meals(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, meal_type TEXT NOT NULL, portion_g REAL NOT NULL CHECK(portion_g>0), calories REAL NOT NULL CHECK(calories>=0), protein REAL NOT NULL CHECK(protein>=0), carbs REAL NOT NULL CHECK(carbs>=0), fat REAL NOT NULL CHECK(fat>=0), fibre REAL NOT NULL DEFAULT 0 CHECK(fibre>=0), notes TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'user-entered', created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY CHECK(id=1), calories REAL NOT NULL, protein REAL NOT NULL, carbs REAL NOT NULL, fat REAL NOT NULL, fibre REAL NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS foods(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, aliases TEXT NOT NULL, calories REAL NOT NULL, protein REAL NOT NULL, carbs REAL NOT NULL, fat REAL NOT NULL, fibre REAL NOT NULL, source TEXT NOT NULL, basis_g REAL NOT NULL DEFAULT 100);
        CREATE INDEX IF NOT EXISTS idx_meals_created_at ON meals(created_at);
        ''')
        if not c.execute('SELECT 1 FROM goals WHERE id=1').fetchone(): c.execute('INSERT INTO goals VALUES(1,2000,125,250,70,30,?)',(now_iso(),))
        if not c.execute('SELECT 1 FROM settings WHERE id=1').fetchone(): c.execute('INSERT INTO settings VALUES(1,?,?)', (json.dumps({'language':'en','dark':False,'units':'grams','ranges':True,'saveHistory':True}), now_iso()))
        for name,aliases,kcal,p,carb,fat,fibre,source in SEED_FOODS:
            c.execute('INSERT OR IGNORE INTO foods(name,aliases,calories,protein,carbs,fat,fibre,source,basis_g) VALUES(?,?,?,?,?,?,?,?,100)',(name,aliases,kcal,p,carb,fat,fibre,source))
init_db()

class MealIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1,max_length=180)
    meal_type: str = Field(default='Lunch', pattern='^(Breakfast|Lunch|Dinner|Snack)$')
    portion_g: float = Field(gt=0, le=10000)
    calories: float = Field(ge=0, le=30000)
    protein: float = Field(ge=0, le=2000)
    carbs: float = Field(ge=0, le=3000)
    fat: float = Field(ge=0, le=2000)
    fibre: float = Field(default=0, ge=0, le=1000)
    notes: str = Field(default='', max_length=3000)
    source: str = Field(default='user-entered', max_length=120)
class GoalsIn(BaseModel):
    calories: float = Field(gt=0,le=10000); protein: float=Field(gt=0,le=500); carbs: float=Field(gt=0,le=1000); fat: float=Field(gt=0,le=400); fibre: float=Field(gt=0,le=150)
class SettingsIn(BaseModel):
    language: str = 'en'; dark: bool = False; units: str = 'grams'; ranges: bool = True; saveHistory: bool = True
class ChatIn(BaseModel):
    message: str = Field(min_length=1,max_length=4000)
    language: str = Field(default='en',pattern='^(en|hi|hinglish)$')
    context: list[dict[str,Any]] = Field(default_factory=list,max_length=30)

@app.get('/api/health')
def health():
    return {'status':'ok','database':'sqlite','vision_configured':bool(os.getenv('OPENAI_API_KEY')),'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'nutrition_reference_table':'starter subset; not full IFCT/USDA import','timestamp':now_iso()}

@app.get('/api/foods')
def foods(q: str = ''):
    with db() as c:
        rows=c.execute('SELECT id,name,aliases,calories,protein,carbs,fat,fibre,source,basis_g FROM foods WHERE name LIKE ? OR aliases LIKE ? ORDER BY name LIMIT 100',(f'%{q}%',f'%{q}%')).fetchall()
    return [dict(r) for r in rows]

@app.get('/api/meals')
def list_meals():
    with db() as c: rows=c.execute('SELECT * FROM meals ORDER BY created_at DESC,id DESC LIMIT 1000').fetchall()
    return [dict(r) for r in rows]

@app.post('/api/meals',status_code=201)
def create_meal(m: MealIn):
    with db() as c:
        cur=c.execute('INSERT INTO meals(name,meal_type,portion_g,calories,protein,carbs,fat,fibre,notes,source,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(m.name.strip(),m.meal_type,m.portion_g,m.calories,m.protein,m.carbs,m.fat,m.fibre,m.notes,m.source,now_iso()))
        row=c.execute('SELECT * FROM meals WHERE id=?',(cur.lastrowid,)).fetchone()
    return dict(row)

@app.put('/api/meals/{meal_id}')
def update_meal(meal_id:int,m:MealIn):
    with db() as c:
        cur=c.execute('UPDATE meals SET name=?,meal_type=?,portion_g=?,calories=?,protein=?,carbs=?,fat=?,fibre=?,notes=?,source=? WHERE id=?',(m.name.strip(),m.meal_type,m.portion_g,m.calories,m.protein,m.carbs,m.fat,m.fibre,m.notes,m.source,meal_id))
        if cur.rowcount==0: raise HTTPException(404,'Meal record not found')
        row=c.execute('SELECT * FROM meals WHERE id=?',(meal_id,)).fetchone()
    return dict(row)

@app.delete('/api/meals/{meal_id}')
def delete_meal(meal_id:int):
    with db() as c:
        cur=c.execute('DELETE FROM meals WHERE id=?',(meal_id,))
        if cur.rowcount==0: raise HTTPException(404,'Meal record not found')
    return {'deleted':True,'id':meal_id}

@app.get('/api/goals')
def get_goals():
    with db() as c: r=c.execute('SELECT calories,protein,carbs,fat,fibre,updated_at FROM goals WHERE id=1').fetchone()
    return dict(r)

@app.put('/api/goals')
def put_goals(g:GoalsIn):
    with db() as c:
        c.execute('UPDATE goals SET calories=?,protein=?,carbs=?,fat=?,fibre=?,updated_at=? WHERE id=1',(g.calories,g.protein,g.carbs,g.fat,g.fibre,now_iso()))
        r=c.execute('SELECT calories,protein,carbs,fat,fibre,updated_at FROM goals WHERE id=1').fetchone()
    return dict(r)

@app.get('/api/settings')
def get_settings():
    with db() as c: r=c.execute('SELECT payload,updated_at FROM settings WHERE id=1').fetchone()
    return {**json.loads(r['payload']),'updated_at':r['updated_at']}
@app.put('/api/settings')
def put_settings(s:SettingsIn):
    if s.language not in ('en','hi','hinglish'): raise HTTPException(422,'Unsupported language')
    if s.units not in ('grams','household'): raise HTTPException(422,'Unsupported portion unit')
    with db() as c: c.execute('UPDATE settings SET payload=?,updated_at=? WHERE id=1',(s.model_dump_json(),now_iso()))
    return {**s.model_dump(),'updated_at':now_iso()}

async def openai_client():
    key=os.getenv('OPENAI_API_KEY')
    if not key: raise HTTPException(503,'AI is not configured. Add OPENAI_API_KEY to backend/.env and restart the backend. No demo result was generated.')
    try:
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=key,timeout=float(os.getenv('OPENAI_TIMEOUT_SECONDS','45')))
    except Exception as e: raise HTTPException(503,f'AI client could not be initialized: {type(e).__name__}')

def extract_json(text:str)->dict:
    try: return json.loads(text)
    except json.JSONDecodeError:
        match=re.search(r'\{.*\}',text,re.S)
        if not match: raise HTTPException(502,'Vision model returned an invalid structured response. Please retry with a clearer image.')
        try:return json.loads(match.group(0))
        except json.JSONDecodeError: raise HTTPException(502,'Vision model response could not be parsed safely.')

def match_food(name:str):
    clean=re.sub(r'[^a-z0-9\s-]','',name.lower()).strip()
    with db() as c: rows=c.execute('SELECT * FROM foods').fetchall()
    for r in rows:
        aliases=[r['name'].lower()]+[x.strip().lower() for x in r['aliases'].split('|')]
        if clean in aliases or any(a and (a in clean or clean in a) for a in aliases if len(a)>3): return dict(r)
    return None

def calculate(food:dict,portion:float)->dict:
    ratio=portion/float(food.get('basis_g') or 100)
    return {k:round(float(food[k])*ratio,2) for k in ('calories','protein','carbs','fat','fibre')}

@app.post('/api/analyze')
async def analyze(image:UploadFile=File(...),language:str='en'):
    if image.content_type not in ALLOWED_MIME: raise HTTPException(415,'Unsupported image type. Upload a JPG, PNG, or WEBP image.')
    raw=await image.read(MAX_IMAGE_BYTES+1)
    if not raw: raise HTTPException(400,'The uploaded image is empty.')
    if len(raw)>MAX_IMAGE_BYTES: raise HTTPException(413,f'Image is too large. Maximum allowed size is {MAX_IMAGE_BYTES//(1024*1024)} MB.')
    try:
        im=Image.open(BytesIO(raw)); im.verify()
        im=Image.open(BytesIO(raw))
        if im.width<32 or im.height<32: raise HTTPException(400,'Image dimensions are too small. Use a clear food photo.')
        if im.width*im.height>30_000_000: raise HTTPException(413,'Image dimensions are too large. Resize the image and retry.')
    except HTTPException: raise
    except (UnidentifiedImageError,OSError): raise HTTPException(400,'File bytes are not a valid supported image. Please select a real image file.')
    if language not in ('en','hi','hinglish'): language='en'
    client=await openai_client()
    mime=image.content_type
    data_url=f'data:{mime};base64,{base64.b64encode(raw).decode("ascii")}'
    prompt='''Inspect the actual uploaded food photograph. Return JSON only, no markdown, with this schema: {"items":[{"name":"short canonical food name","visible_ingredients":["visually supported ingredient only"],"portion_g":150,"confidence":0.0,"portion_low_g":100,"portion_high_g":200,"preparation":"unknown or visible evidence","uncertain_factors":["..."],"notes":"..."}],"assumptions":"...","clarifying_questions":["..."]}. Identify only foods visibly supported by the image; for mixed Indian thali list distinct visible items separately. Do not infer exact hidden ingredients, oil/ghee, recipe, or exact weight. Use conservative confidence from 0 to 1. If image is not food or is ambiguous, return items=[] and explain in assumptions. Portions are rough estimates. Respond in requested language where appropriate: '''+language+'''. Limit items to 12. Never return example/demo labels unrelated to the image.'''
    try:
        response=await client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4o-mini'),temperature=0.1,max_tokens=1600,response_format={'type':'json_object'},messages=[{'role':'system','content':'You are a cautious food-vision analysis component. Do not claim exact nutrition from pixels. Output valid JSON only.'},{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':data_url,'detail':'high'}}]}])
        text=response.choices[0].message.content or '{}'
    except HTTPException: raise
    except Exception as e:
        code=getattr(e,'status_code',None)
        err_code=str(getattr(e,'code','') or '')
        err_text=str(e).lower()
        if code==401: raise HTTPException(502,'OpenAI API authentication failed. Check that backend/.env contains a valid, active OPENAI_API_KEY, then restart the backend.')
        if code==429:
            if 'insufficient_quota' in err_code.lower() or 'insufficient_quota' in err_text or 'quota' in err_text or 'billing' in err_text:
                raise HTTPException(503,'OpenAI API quota/billing is unavailable for this key or project. This is an account billing/usage limit, not a camera or upload bug. Check https://platform.openai.com/settings/organization/billing and https://platform.openai.com/usage, confirm the API project has available credit and a usage limit, then retry. ChatGPT subscription is separate from API billing.')
            raise HTTPException(503,'OpenAI API rate limit reached. Wait briefly and retry, or review project rate limits at https://platform.openai.com/settings/organization/limits.')
        raise HTTPException(502,f'Vision analysis failed ({type(e).__name__}). Check API connectivity/model configuration and retry.')
    data=extract_json(text)
    items=data.get('items')
    if not isinstance(items,list): raise HTTPException(502,'Vision response is missing a valid items list.')
    result=[]
    for it in items[:12]:
        if not isinstance(it,dict) or not isinstance(it.get('name'),str) or not it['name'].strip(): continue
        try: portion=max(1,min(10000,float(it.get('portion_g',150))))
        except (TypeError,ValueError): portion=150
        try: confidence=max(0,min(1,float(it.get('confidence',0))))
        except (TypeError,ValueError): confidence=0
        food=match_food(it['name'])
        nutrition=calculate(food,portion) if food else None
        low=max(1,float(it.get('portion_low_g',portion*.7) or portion*.7)); high=max(low,float(it.get('portion_high_g',portion*1.3) or portion*1.3))
        result.append({'name':it['name'].strip(),'visible_ingredients':[x for x in it.get('visible_ingredients',[]) if isinstance(x,str)][:20],'portion_g':round(portion),'portion_range_g':[round(low),round(high)],'confidence':confidence,'preparation':str(it.get('preparation','unknown'))[:200],'uncertain_factors':[x for x in it.get('uncertain_factors',[]) if isinstance(x,str)][:10],'notes':str(it.get('notes',''))[:500],'nutrition':nutrition,'calories':nutrition['calories'] if nutrition else None,'protein':nutrition['protein'] if nutrition else None,'carbs':nutrition['carbs'] if nutrition else None,'fat':nutrition['fat'] if nutrition else None,'fibre':nutrition['fibre'] if nutrition else None,'source':food['source'] if food else None,'database_match':food['name'] if food else None,'needs_food_match':food is None,'nutrition_range':({k:[round(v*.85,1),round(v*1.15,1)] for k,v in nutrition.items()} if nutrition else None)})
    return {'items':result,'assumptions':str(data.get('assumptions','Portion and hidden ingredients are uncertain.'))[:1500],'clarifying_questions':[str(q)[:300] for q in data.get('clarifying_questions',[]) if isinstance(q,str)][:6],'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'image_mime':mime,'image_bytes':len(raw),'created_at':now_iso(),'notice':'Nutrition values are calculated only when a matching starter reference record exists. Unmatched foods need a verified database match; do not treat this starter table as a full IFCT/USDA import.'}

@app.post('/api/chat')
async def chat(payload:ChatIn):
    client=await openai_client()
    lang={'en':'English','hi':'Hindi','hinglish':'Hinglish (Hindi-English mix)'}[payload.language]
    # Bound context length; do not send arbitrary oversized client content.
    context=[]
    for item in payload.context[:15]:
        if isinstance(item,dict): context.append({k:item.get(k) for k in ('name','meal_type','portion_g','calories','protein','carbs','fat','fibre','created_at') if k in item})
    system=f'''You are Food AI Intelligence, a cautious nutrition information assistant. Reply in {lang}. Use saved meal context only as user-provided records, not as verified lab measurements. Never invent a database citation, food value, or meal record. Explain uncertainty and ask clarifying questions if portion/preparation materially affects estimates. This is general nutrition information, not medical diagnosis. If context is empty, say you do not have saved meal records to summarize. Keep answers practical and clear.'''
    try:
        response=await client.chat.completions.create(model=os.getenv('OPENAI_MODEL','gpt-4o-mini'),temperature=.2,max_tokens=800,messages=[{'role':'system','content':system},{'role':'user','content':'Saved meal context JSON:\n'+json.dumps(context,ensure_ascii=False)+'\n\nUser question:\n'+payload.message}])
        answer=response.choices[0].message.content
        if not answer: raise HTTPException(502,'Assistant returned an empty response.')
        return {'answer':answer,'model':os.getenv('OPENAI_MODEL','gpt-4o-mini'),'created_at':now_iso()}
    except HTTPException: raise
    except Exception as e:
        code=getattr(e,'status_code',None)
        if code==401: raise HTTPException(502,'AI authentication failed. Check OPENAI_API_KEY.')
        if code==429: raise HTTPException(503,'AI rate limit or quota reached. Check API billing and limits.')
        raise HTTPException(502,f'Assistant request failed ({type(e).__name__}). Retry after checking backend logs.')

@app.get('/api/analytics/weekly')
def weekly():
    with db() as c: rows=c.execute("SELECT substr(created_at,1,10) day, SUM(calories) calories, SUM(protein) protein, SUM(carbs) carbs, SUM(fat) fat, SUM(fibre) fibre, COUNT(*) meals FROM meals WHERE created_at >= ? GROUP BY substr(created_at,1,10) ORDER BY day",(datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).isoformat(),)).fetchall()
    return [dict(r) for r in rows]
