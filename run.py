"""
BI Dashboard AI - Single file launcher
Run: python run.py
"""
import subprocess, sys, os, time, signal, sqlite3, random, shutil
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# 1. Install deps
def install_deps():
    deps = ["fastapi","uvicorn","groq","pandas","numpy","streamlit","plotly","python-multipart","requests"]
    print("Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", *deps, "-q"], check=True)
    print("Dependencies ready.\n")

install_deps()
import requests

# 2. Copy pre-written backend and frontend files
BACKEND_TEMPLATE = os.path.join(BASE, "backend_template.py")
FRONTEND_TEMPLATE = os.path.join(BASE, "frontend_template.py")

os.makedirs(os.path.join(BASE, "backend"), exist_ok=True)
os.makedirs(os.path.join(BASE, "frontend"), exist_ok=True)
os.makedirs(os.path.join(BASE, "data"), exist_ok=True)

open(os.path.join(BASE, "backend", "__init__.py"), "w").close()
open(os.path.join(BASE, "frontend", "__init__.py"), "w").close()

if os.path.exists(BACKEND_TEMPLATE):
    shutil.copy(BACKEND_TEMPLATE, os.path.join(BASE, "backend", "main.py"))
    print("backend/main.py ready")
else:
    print("ERROR: backend_template.py not found next to run.py")
    sys.exit(1)

if os.path.exists(FRONTEND_TEMPLATE):
    shutil.copy(FRONTEND_TEMPLATE, os.path.join(BASE, "frontend", "app.py"))
    print("frontend/app.py ready")
else:
    print("ERROR: frontend_template.py not found next to run.py")
    sys.exit(1)

# 3. Create sample database
DB_PATH = os.path.join(BASE, "data", "business.db")

def create_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
        DROP TABLE IF EXISTS sales; DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products; DROP TABLE IF EXISTS employees;
        DROP TABLE IF EXISTS marketing_campaigns;
    """)
    c.execute("CREATE TABLE products (product_id INTEGER PRIMARY KEY, product_name TEXT, category TEXT, unit_price REAL, cost_price REAL)")
    products = [
        (1,"Laptop Pro","Electronics",1299.99,800),(2,"Wireless Mouse","Electronics",29.99,10),
        (3,"Office Chair","Furniture",349.99,180),(4,"Standing Desk","Furniture",599.99,320),
        (5,"Coffee Maker","Appliances",89.99,40),(6,"Headphones","Electronics",199.99,90),
        (7,"Monitor 4K","Electronics",499.99,280),(8,"Keyboard Mech","Electronics",149.99,65),
        (9,"Desk Lamp","Furniture",59.99,22),(10,"Webcam HD","Electronics",79.99,35),
        (11,"Blender Pro","Appliances",119.99,55),(12,"Air Purifier","Appliances",249.99,120),
    ]
    c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)
    c.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, customer_name TEXT, email TEXT, region TEXT, city TEXT, segment TEXT, join_date TEXT)")
    regions = ["North","South","East","West","Central"]
    cities = {"North":["Chicago","Detroit","Minneapolis"],"South":["Atlanta","Miami","Dallas"],
              "East":["New York","Boston","Philadelphia"],"West":["Los Angeles","Seattle","San Francisco"],
              "Central":["Denver","Kansas City","Oklahoma City"]}
    segs = ["Enterprise","SMB","Startup","Individual"]
    random.seed(42)
    custs = []
    for i in range(1, 501):
        r = random.choice(regions)
        custs.append((i,f"Customer_{i:03d}",f"c{i}@ex.com",r,random.choice(cities[r]),
                      random.choice(segs),(datetime.now()-timedelta(days=random.randint(0,1000))).strftime("%Y-%m-%d")))
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", custs)
    c.execute("CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, product_id INTEGER, customer_id INTEGER, sale_date TEXT, quantity INTEGER, unit_price REAL, discount REAL, total_amount REAL, profit REAL, channel TEXT)")
    channels = ["Online","In-Store","Partner","Direct Sales"]
    sales = []
    s, e = datetime(2023,1,1), datetime(2024,12,31)
    for i in range(1, 3001):
        pid=random.randint(1,12); p=products[pid-1]; qty=random.randint(1,10)
        disc=random.choice([0,.05,.10,.15,.20]); total=round(qty*p[3]*(1-disc),2)
        sales.append((i,pid,random.randint(1,500),(s+timedelta(days=random.randint(0,730))).strftime("%Y-%m-%d"),
                      qty,p[3],disc,total,round(total-qty*p[4],2),random.choice(channels)))
    c.executemany("INSERT INTO sales VALUES (?,?,?,?,?,?,?,?,?,?)", sales)
    c.execute("CREATE TABLE employees (employee_id INTEGER PRIMARY KEY, name TEXT, department TEXT, role TEXT, salary REAL, hire_date TEXT, performance_score REAL, region TEXT)")
    depts=["Sales","Marketing","Engineering","HR","Finance","Operations"]
    bs={"Sales":65000,"Marketing":70000,"Engineering":95000,"HR":60000,"Finance":75000,"Operations":68000}
    emps=[]
    for i in range(1,101):
        d=random.choice(depts)
        emps.append((i,f"Emp_{i:03d}",d,f"{d} Analyst",round(bs[d]+random.randint(-10000,30000),-2),
                     (datetime.now()-timedelta(days=random.randint(0,2000))).strftime("%Y-%m-%d"),
                     round(random.uniform(2.5,5.0),1),random.choice(regions)))
    c.executemany("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?)", emps)
    c.execute("CREATE TABLE marketing_campaigns (campaign_id INTEGER PRIMARY KEY, campaign_name TEXT, channel TEXT, start_date TEXT, end_date TEXT, budget REAL, spent REAL, leads_generated INTEGER, conversions INTEGER, revenue_attributed REAL)")
    mch=["Email","Social Media","PPC","SEO","TV","Radio"]
    camps=[]
    for i in range(1,31):
        ch=random.choice(mch); b=round(random.uniform(5000,100000),2); sp=round(b*random.uniform(.7,1),2)
        leads=random.randint(100,5000); conv=int(leads*random.uniform(.05,.25))
        sd=s+timedelta(days=random.randint(0,500)); ed=sd+timedelta(days=random.randint(30,90))
        camps.append((i,f"Campaign_{i:02d}",ch,sd.strftime("%Y-%m-%d"),ed.strftime("%Y-%m-%d"),
                      b,sp,leads,conv,round(conv*random.uniform(100,1000),2)))
    c.executemany("INSERT INTO marketing_campaigns VALUES (?,?,?,?,?,?,?,?,?,?)", camps)
    conn.commit(); conn.close()
    print("Sample database created.\n")

if not os.path.exists(DB_PATH):
    print("Creating sample database...")
    create_database()
else:
    print("Database already exists.\n")

# 4. Start FastAPI
print("Starting FastAPI backend on port 8000...")
backend_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
    cwd=BASE
)

print("Waiting for backend...")
for _ in range(25):
    try:
        if requests.get("http://localhost:8000/health", timeout=1).status_code == 200:
            print("Backend ready at http://localhost:8000\n")
            break
    except Exception:
        pass
    time.sleep(1)

# 5. Start Streamlit
print("Starting Streamlit frontend...")
print("Open: http://localhost:8501\n")
print("Press Ctrl+C to stop.\n")

frontend_proc = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run",
     os.path.join(BASE, "frontend", "app.py"),
     "--server.port", "8501",
     "--server.address", "0.0.0.0",
     "--server.headless", "true",
     "--theme.base", "light",
     "--theme.primaryColor", "#4f46e5",
     "--theme.backgroundColor", "#f5f7fa",
     "--theme.secondaryBackgroundColor", "#ffffff",
     "--theme.textColor", "#1e293b"],
    cwd=BASE
)

def shutdown(sig, frame):
    print("\nShutting down...")
    frontend_proc.terminate()
    backend_proc.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
frontend_proc.wait()
