"""
"""

import time
from datetime import datetime, timedelta
from enum import Enum
from flask import Flask, request, redirect, render_template, session
import redis
import csv
import random
import bcrypt

r = redis.Redis(
    host='redis-10494.c53.west-us.azure.cloud.redislabs.com',
    port=10494,
    decode_responses=True,
    username="default",
    password="x3IvJ1v7Y9KRTrf1Bnvag8lrpsaafEIb",
)

usersPath = './data/users.csv'
equipPath = './data/equipment.csv'
rentPath = './data/sample_rentals.csv'
questionsPath = './data/security_questions.csv'

user = None
name = None
admin = False
questions = None
catalogue = None
rentals = None

app = Flask(__name__)

@app.context_processor
def inject_user():
    global user, name, admin
    return {'user': user, 'name': name, 'is_admin': admin}

@app.route('/')
@app.route('/<path:path>')
def f_default(path=None):
    if user:
        return redirect('/user/rentals')
    return redirect('/auth/login')

@app.route('/auth/signup', methods=['GET', 'POST'])
def f_signup():
    global questions
    if not questions: questions = getSecQ()
    
    if request.method == 'POST':
        res, msg = signup(request.form, request.remote_addr);
        return render_template('auth/signup.html', questions=questions, res=res, msg=msg)
    
    return render_template('auth/signup.html', questions=questions, res=True, msg='start')

@app.route('/auth/login', methods=['GET', 'POST'])
def f_login():
    global user
    if user:
        return redirect('/user/rentals');
    
    if request.method == 'POST':
        res, msg = login(request.form, request.remote_addr)
        if res:
            return redirect('/user/rentals');
        return render_template('auth/login.html', msg=msg)
    
    return render_template('auth/login.html')

@app.route('/auth/reset', methods=['GET', 'POST'])
def f_reset():
    if request.method == 'POST':
        if 'answer' in request.form:
            res, msg = resetPassword(request.form, request.remote_addr)
            return render_template('auth/reset.html', email=request.form['email'], question=request.form['question'], res=res, msg=msg)
        
        if 'email' in request.form:
            question = requestResetPassword(request.form['email'])
            return render_template('auth/reset.html', email=request.form['email'], question=question)
    
    return render_template('auth/reset.html')

@app.route('/logout')
def f_logout():
    logout();
    return redirect('/')

@app.route('/catalogue')
def f_catalogue():
    global user, catalogue
    if not user:
        return redirect('/')
    
    if not catalogue:
        updateCatalogue()
    
    minDate = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template('catalogue.html', catalogue=catalogue, minDate=minDate)

@app.route('/user/rentals')
def f_rentals():
    global user, rentals
    if not user:
        return redirect('/')
    
    if not rentals:
        updateRentals()
    
    return render_template('user/rentals.html', rentals=rentals)

@app.route('/rentals/add', methods=['POST'])
def f_rentals_add():
    global user
    if not user:
        return redirect('/')
    
    addRental(request.form, request.remote_addr)
    return redirect('/user/rentals')

@app.route('/rentals/remove', methods=['POST'])
def f_rentals_remove():
    global user
    if not user:
        return redirect('/')
    
    delRental(request.form, request.remote_addr)
    return redirect('/user/rentals')

@app.route('/admin/equipment')
def f_admin_equipment():
    global user, admin
    if not user or not admin:
        return redirect('/')
    return render_template('admin/equipment.html')

@app.route('/admin/users')
def f_admin_users():
    global user, admin
    if not user or not admin:
        return redirect('/')
    users = r.smembers('users:all')
    return render_template('admin/users.html', users=users)

# --- Helper function ---

def wipeRedis():
    """
    Clear all data from Redis database. WARNING: Deletes everything!
    Used for testing to start with clean slate.
    """
    r.flushall()

def loadFile(path):
    """
    Read CSV file and return list of dictionaries.
    
    Args:
        path (str): Path to CSV file
    
    Returns:
        list: List of row dictionaries from CSV
    """
    res = []
    with open(path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            res.append(row)
            
    return res

def loadDataFromCSV():
    """
    Load all data from CSV files (users, equipment, rentals, security questions) into Redis.
    Orchestrates all CSV loading functions in correct order.
    
    Returns:
        bool: True if all data loaded successfully, False otherwise
    """
    print('Loading data from CSV files into Redis')
    try:
        loadSecurityQuestionCSV()
        loadUsersCSV()
        loadEquipmentCSV()
        loadRentalsCSV()
        print('Data loaded successfully')
        return True
    
    except Exception as e:
        print(f'Error loading data from CSV: {e}')
        return False
    return

def loadSecurityQuestionCSV():
    """
    Load security questions from CSV into Redis SET.
    Used for random selection during signup.
    
    Returns:
        bool: True if successful, False on error
    """
    try:
        questions = loadFile(questionsPath)
        
        for q in questions:
            r.sadd('security:questions', q['question'])
        
        print(f"Loaded {len(questions)} security questions")
        return True
    
    except Exception as e:
        print(f"Security questions error: {e}")
        return False

def loadUsersCSV():
    """
    Load user accounts from CSV and register them in Redis.
    Handles admin promotion for flagged users.
    
    Returns:
        bool: True if successful, False on error
    """
    try:
        users = loadFile(usersPath)
        
        for user in users:
            email = user['email']
            password = user['password']
            fName = user['first_name']
            admin = int(user['is_admin'])
            secQ = user['security_question']
            secA = user['security_answer']
            
            req = {
                'email': email,
                'fname': fName,
                'password': password,
                'sq': secQ,
                'sa': secA
            }
            
            if signup(req, 'from_csv'):
                if admin:
                    addAdmin(email)
        
        print(f"Loaded {len(users)} users")
        return True
    
    except Exception as e:
        print(f"Users loading error: {e}")
        return False
    return

def loadEquipmentCSV():
    """
    Load equipment catalogue from CSV into Redis.
    Creates equipment HASHes and adds to equipment index.
    
    Returns:
        bool: True if successful, False on error
    """
    try:
        equipment = loadFile(equipPath)
        
        for item in equipment:
            equipId = item['id']
            
            data = {
                'name': item['name'],
                'desc': item['description'],
                'price': item['price'],
                'stock': int(item['stock']),
                'creAt': int(item['created_at'])
            }
            
            addEquipment(data, equipId=equipId)
        
        print(f"Loaded {len(equipment)} equipment items")
        return True
    
    except Exception as e:
        print(f"Equipment loading error: {e}")
        return False

def loadRentalsCSV():
    """
    Load sample rentals from CSV into Redis.
    Populates user rental lists with pre-loaded rentals for testing.
    
    Returns:
        bool: True if successful, False on error
    """
    try:
        global user
        rentals = loadFile(rentPath)
        
        for rental in rentals:
            email = rental['email']
            equipId = rental['equipment_id']
            qty = rental['quantity']
            duration = rental['duration']
            
            user = email
            returnDate = (datetime.now() + timedelta(days=int(duration))).strftime('%Y-%m-%d')
            
            req = {
                'equipId': equipId,
                'qty': qty,
                'returnDate': returnDate
            }
            
            addRental(req, 'from_csv')
        
        print(f"Loaded {len(rentals)} sample rentals")
        return True
    
    except Exception as e:
        print(f"Sample rentals error: {e}")
        return False

def getNewId():
    """
    Generate new equipment ID by incrementing counter in Redis.
    
    Returns:
        int: Next available equipment ID
    """
    return r.incr('equipment:nextId')

def getHash(password):
    """
    Hash password using bcrypt with random salt.
    
    Args:
        password (str): Plain text password
    
    Returns:
        str: Bcrypt hashed password (encoded as string)
    """
    salt = bcrypt.gensalt()
    pwd = password.encode('utf-8')
    return bcrypt.hashpw(pwd, salt).decode('utf-8')

def isAccount(email):
    """
    Check if user account exists in Redis.
    
    Args:
        email (str): User email address
    
    Returns:
        bool: True if account exists, False otherwise
    """
    return bool(r.exists(f'auth:{email}'))

def isAdmin(email):
    """
    Check if user has admin privileges.
    
    Args:
        email (str): User email address
    
    Returns:
        bool: True if user is admin, False otherwise
    """
    return bool(r.sismember('admins', email))

def addLog(email, action, value, details=''):
    """
    Log user action with timestamp to Redis LIST.
    Format: timestamp|action|value|details
    
    Args:
        email (str): User email for log tracking
        action (str): Action type (login, signup, rental, etc)
        value (str): Action result or target
        details (str): Optional additional details (IP, error, etc)
    """
    data = f'{time.time()}|{action}|{value}'
    if (details): data = data + f'|{details}'
    
    print(f'[LOG - {email}]: {data}')
    r.lpush(f'logs:{email}', data)

def getSecQ():
    """
    Get all available security questions from Redis.
    
    Returns:
        set: Set of security question strings
    """
    return r.smembers('security:questions')


# --- Authentication / Authorisation ---

def signup(req, ip):
    """
    Register new user account.
    Hashes password and security answer, stores in Redis HASH.
    
    Args:
        req (dict): Form data with keys: fname, email, password, sq, sa
        ip (str): User IP address for logging
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        fName = req['fname']
        email = req['email']
        plainPassword = req['password']
        question = req['sq']
        answer = req['sa']
        
        if isAccount(email):
            addLog(email, 'signup', 'failed:email_exists', f'ip:{ip}')
            return False, 'Email already exists';
        else:
            data = {
                'name': fName,
                'pass': getHash(plainPassword),
                'secQ': question,
                'secA': getHash(answer),
                'creAt': int(time.time()),
            }
            
            res = bool(r.hset(f'auth:{email}', mapping=data))
            if res: r.sadd('user:all', email)
            
        addLog(email, 'signup', f'success:{res}', f'ip:{ip}')
        return res, ''
    
    except Exception as e:
        print(f'Signup error {e}')
        addLog(email, 'signup', f'success:{False}', f'error:{e}, ip:{ip}')
        return False, 'Something went wrong'


def login(req, ip):
    """
    Authenticate user with email and password.
    Verifies password against bcrypt hash in Redis.
    Sets global user and admin flag on success.
    
    Args:
        req (dict): Form data with keys: email, password
        ip (str): User IP address for logging
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        global user, name, admin
        if user:
            return False, f'Already logged in as {user}'
        else:
            email = req['email']
            passw = req['password']
            hashPass, fname = r.hmget(f'auth:{email}', ['pass', 'name']);
            
            if not hashPass:
                # DO NOT return 'Invalid email' = enumeration risk!
                return False, 'Invalid credentials'
            else:
                res = bcrypt.checkpw(passw.encode('utf-8'), hashPass.encode('utf-8'))
                
                if res:
                    user = email
                    name = fname
                    if isAdmin(user): 
                        admin = True
            
        addLog(email, 'login', f'success:{res}', f'ip:{ip}')
        # DO NOT return 'Invalid password' = enumeration risk!
        return res, '' if res else 'Invalid credentials'
    
    except (AttributeError, TypeError) as e:
        print(f"Login error: {e}")
        addLog(email, 'login', f'success:{False}', f'error:{e}, ip:{ip}')
        return False, 'Something went wrong'
    
def logout():
    """
    Clear user session by resetting all global user variables.
    """
    global user, name, admin, catalogue, rentals
    user = None;
    name = None;
    admin = False;
    catalogue = None;
    rentals = None;

# --- Password Reset ---

def requestResetPassword(email):
    """
    Retrieve security question for password reset.
    
    Args:
        email (str): User email
    
    Returns:
        str: Security question text, or None if account not found
    """
    return r.hget(f'auth:{email}', 'secQ')

def resetPassword(req, ip):
    """
    Reset password after verifying security answer.
    
    Args:
        req (dict): Form data with keys: email, answer, pass1, pass2
        ip (str): User IP address for logging
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        pass1 = req['pass1']
        pass2 = req['pass2']
        
        if (pass1 != pass2):
            return False, 'Passwords need to match'
        
        email = req['email']
        answer = req['answer']
        
        secA = r.hget(f'auth:{email}', 'secA')
        
        if not bcrypt.checkpw(answer.encode('utf-8'), secA.encode('utf-8')):
            addLog(email, 'password_reset', 'failed:wrong_answer', f'ip:{ip}')
            return False, 'Incorrect answer'
        
        newPass = getHash(pass1);
        r.hset(f'auth:{email}', 'pass', newPass)
        addLog(email, 'password_reset', f'success', f'ip:{ip}')
        return True, ''
        
    except Exception as e:
        addLog(email, 'password_reset', 'error', f'{str(e)}, ip:{ip}')
        print(f'Password reset error: {e}')
        return False, 'Something went wrong'


# --- Rental Functions ---

def addRental(req, ip):
    """
    Add equipment to user's rental list.
    Validates stock availability, decrements inventory, creates rental record.
    
    Args:
        req (dict): Form data with keys: equipId, qty, returnDate (YYYY-MM-DD)
        ip (str): User IP address for logging
    
    Returns:
        bool: True if rental added successfully, False otherwise
    """
    try:
        global user
        equipId = req['equipId']
        qty = req['qty']
        returnDate = req['returnDate']

        expiresAt = int(datetime.strptime(str(returnDate), '%Y-%m-%d').timestamp())
    
        stock = r.hget(f'equipment:{equipId}', 'stock')
        
        if stock is None:
            print(f'Equipment {equipId} not found')
            addLog(user, 'add_rental', f'failed:{equipId}', f'equipment_not_found, ip:{ip}')
            return False
        
        qty = int(qty)
        
        if int(stock) < qty:
            print(f'Equipment {equipId} out of stock')
            addLog(user, 'add_rental', f'failed:{equipId}', f'out_of_stock:{stock}, ip:{ip}')
            return False
        
        rentedAt = int(time.time())
        
        if int(expiresAt) < rentedAt:
            print('Invalid date')
            return False
        
        rentalId = f"{rentedAt}_{equipId}"
        rentalData = f'{equipId}|{qty}|{rentedAt}|{expiresAt}'
        
        # Update the stock locally so we don't have to fetch again
        global catalogue
        if not catalogue:
            updateCatalogue()
        catalogue[equipId]['stock'] = r.hincrby(f'equipment:{equipId}', 'stock', -qty)
        
        r.hset(f'user:{user}:rentals', rentalId, rentalData)
        r.zadd('rentals:expiring', {f'{user}:{rentalId}': expiresAt})
        
        updateRentals()
        
        addLog(user, 'add_rental', f'success:{rentalId}', f'qty:{qty}, ip:{ip}')
        return True
        
    except Exception as e:
        addLog(user, 'add_rental', f'error:{req['equipId']}', f'{str(e)}, ip:{ip}')
        print(f'Error adding rental: {e}')
        return False

def delRental(req, ip):
    """
    Remove equipment from user's rental list.
    Returns quantity to inventory and deletes rental record.
    
    Args:
        req (dict): Form data with keys: rentalId
        ip (str): User IP address for logging
    
    Returns:
        bool: True if rental removed successfully, False otherwise
    """
    try:
        global user
        rentalId = req['rentalId']
        rentalData = r.hget(f'user:{user}:rentals', rentalId)
        
        if not rentalData:
            print(f'Rental {rentalId} not in rental list')
            addLog(user, 'del_rental', f'failed:{rentalId}', f'not_in_list, ip:{ip}')
            return False
        
        equipId, qty, rentedAt, expiresAt = rentalData.split('|')
        qty = int(qty)
        
        # Update the stock locally so we don't have to fetch again
        global catalogue
        if not catalogue:
            updateCatalogue()
            
        catalogue[equipId]['stock'] = r.hincrby(f'equipment:{equipId}', 'stock', qty)
        
        r.hdel(f'user:{user}:rentals', rentalId)
        r.zrem('rentals:expiring', f'{user}:{rentalId}')
        
        updateRentals()
        
        addLog(user, 'del_rental', f'success:{rentalId}', f'qty:{qty}, ip:{ip}')
        return True
        
    except Exception as e:
        addLog(user, 'del_rental', f'error:{rentalId}', f'{str(e)}, ip:{ip}')
        print(f'Error removing rental: {e}')
        return False

def updateRentals():
    """
    Refresh rental list from Redis for currently logged-in user.
    Updates global rentals dictionary.
    """
    global user, rentals
    if not user: return
    rentals = viewRentals()
    
def updateCatalogue():
    """
    Refresh equipment catalogue from Redis.
    Updates global catalogue dictionary with all equipment and current stock.
    """
    global catalogue
    catalogue = getEquipment()

def viewRentals():
    """
    Get formatted rental data for currently logged-in user.
    Fetches rental records and equipment details from Redis using pipeline.
    
    Returns:
        dict: Rental details keyed by rentalId with computed values (price, expiry, etc)
    """
    try:
        global user
        if not user:
            print('No user logged in')
            return {}
        
        rentals = getRentalList(user)
        
        if not rentals:
            print(f'No active rentals')
            return {}
        
        equipIds = set()
        for rentalData in rentals.values():
            equipIds.add(rentalData.split('|')[0])
        
        pipe = r.pipeline()
        for equipId in equipIds:
            pipe.hgetall(f'equipment:{equipId}')
            
        equipments = pipe.execute()
        equipment = dict(zip(equipIds, equipments))
        
        res = {}
        
        for rentalId, rentalData in rentals.items():
            equipId, qty, rentedAt, expiresAt = rentalData.split('|')
            qty = int(qty)
            expiresAt = int(expiresAt)
            rentedAt = int(rentedAt)
            
            equip = equipment[equipId]
            
            now = int(time.time())
            daysLeft = 1 + ((expiresAt - now) // 86400) # 86400s = 1d
            
            expiryDate = datetime.fromtimestamp(expiresAt).strftime("%d/%m/%Y")
            
            daysRented = 1 + (expiresAt - rentedAt) // 86400
            
            total = float(equip['price']) * qty * daysRented
            
            res[rentalId] = {
                'rentalId': rentalId,
                'name': equip['name'],
                'desc': equip['desc'],
                'price': equip['price'],
                'qty': qty,
                'total': f'{total:.2f}',
                'daysRented': daysRented,
                'daysLeft': daysLeft,
                'expiryDate': expiryDate
            }
        
        return res
    
    except Exception as e:
        print(f"Error viewing rentals: {e}")
        return {}

def getRentalList(email):
    """
    Get raw rental data for user (unformatted).
    
    Args:
        email (str): User email
    
    Returns:
        dict: Raw rental HASH {rentalId: "equipId|qty|rentedAt|expiresAt", ...}
    """
    try:
        return r.hgetall(f'user:{email}:rentals')
    except Exception as e:
        print(f'Error getting rental list: {e}')
        return {}

def getEquipment():
    """
    Fetch all equipment from Redis using pipeline for efficiency.
    
    Returns:
        dict: Equipment details keyed by equipId {equipId: {name, desc, price, stock, ...}, ...}
    """
    try:
        equipIds = r.smembers('equipment:all')
        
        pipe = r.pipeline()
        for equipId in equipIds:
            pipe.hgetall(f'equipment:{equipId}')
        res = pipe.execute()
        return dict(zip(equipIds, res))
    
    except Exception as e:
        print(f'Error getting equipment list: {e}')
        return {}

# ---- Admin Actions ----
    
def adminAction(action, email=None, equipId=None, data=None):
    """
    Execute admin action after authorization check.
    Routes to appropriate function based on action string.
    
    Args:
        action (str): Action type (delUser, addAdmin, delAdmin, addEquipment, etc)
        email (str): User email (for user operations)
        equipId (str): Equipment ID (for equipment operations)
        data (dict): Data for add/modify operations
    
    Returns:
        bool: Success status of operation
    """
    try:
        global user, admin
        res = None
        details = None
        
        if not user or not admin:
            res = False
            details = 'unauthorised'
            print('Unauthorised action')
        elif not isAccount(email):
            res = False
            details = 'not_an_account'
            print(f'User {email} does not exist')
        else:
            match action:
                case 'delUser':
                    res = delUser(email);
                case 'addAdmin':
                    res = addAdmin(email);
                case 'delAdmin':
                    res = delAdmin(email);
                case 'addEquipment':
                    res, details = addEquipment(data);
                case 'modEquipment':
                    res, details = modEquipment(equipId, data);
                case 'delEquipment':
                    res, details = delEquipment(equipId);
                case _:
                    res = False
                    details = 'unknown'
                    print(f'Unknown admin action {action}')
        
        addLog(user, 'admin_action', f'{action}:{email}', f'{res}{f':{details}' if details else ''}')
        return res
    except Exception as e:
        print(f'Admin action error: {e}')
        addLog(user, 'admin_action', f'{action}:{email}', f'error:{e}') 
    
# -- Admin Actions: Users --

def delUser(email):
    return bool(r.delete(f'auth:{email}'))

def addAdmin(email):
    return bool(r.sadd('admins', email))

def delAdmin(email):
    return bool(r.srem('admins', email))

# -- Admin Actions: Equipment --

def addEquipment(data, equipId=None):
    if not equipId: equipId = getNewId();

    res = bool(r.hset(f'equipment:{equipId}', mapping=data))
    if res:
        r.sadd('equipment:all', equipId)
        print(f'Added new equipment {data['name']}.')
    
    return res, f'{equipId}:{data['name']}'

def modEquipment(equipId, data):
    res = bool(r.hset(f'equipment:{equipId}', mapping=data))
    print(f'Modifier equipment with ID {equipId}.')
    return res, f'{equipId}:{data['name']}'

def delEquipment(equipId):
    res = bool(r.hdel(f'equipment:{equipId}'))
    if red:
        r.srem('equipment:all', equipId);
        print(f'Removed equipment with ID {equipId}')
    return res, equipId

# --- Testing / Debug ---

def testSystem():
    global user, admin, catalogue, rentals
    
    print("\n" + "="*60)
    print("🧪 TRAILHIRE SYSTEM TEST SUITE")
    print("="*60 + "\n")
    
    # Test 1: Data Loading
    print("TEST 1: CSV Data Loading")
    print("-" * 40)
    wipeRedis()
    if loadDataFromCSV():
        print("✓ CSV data loaded successfully\n")
    else:
        print("✗ CSV loading failed\n")
        return
    
    # Test 2: Login
    print("TEST 2: Authentication - Login")
    print("-" * 40)
    req = {'email': 'john.doe@trailhire.com', 'password': 'SecurePass123!'}
    res, msg = login(req, '127.0.0.1')
    if res:
        print(f"✓ Login successful: {msg}\n")
    else:
        print(f"✗ Login failed: {msg}\n")
        return
    
    # Test 3: Wrong password
    print("TEST 3: Authentication - Wrong Password")
    print("-" * 40)
    req = {'email': 'john.doe@trailhire.com', 'password': 'WrongPassword'}
    res, msg = login(req, '127.0.0.1')
    if not res:
        print(f"✓ Correctly rejected: {msg}\n")
    else:
        print(f"✗ Should have been rejected\n")
    
    # Reset to logged-in state
    user = 'john.doe@trailhire.com'
    
    # Test 4: View Catalogue
    print("TEST 4: Equipment - View Catalogue")
    print("-" * 40)
    updateCatalogue()
    if catalogue and len(catalogue) > 0:
        print(f"✓ Loaded {len(catalogue)} equipment items")
        print(f"  Sample: {list(catalogue.values())[0]['name']}\n")
    else:
        print("✗ Failed to load catalogue\n")
    
    # Test 5: Add Rental
    print("TEST 5: Rental - Add Equipment")
    print("-" * 40)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    req = {
        'equipId': '1',
        'qty': '1',
        'returnDate': tomorrow
    }
    if addRental(req, '127.0.0.1'):
        print(f"✓ Added rental: 1x Equipment #1 for {tomorrow}\n")
    else:
        print("✗ Failed to add rental\n")
    
    # Test 6: View Rentals
    print("TEST 6: Rental - View Rentals")
    print("-" * 40)
    updateRentals()
    if rentals and len(rentals) > 0:
        print(f"✓ Active rentals: {len(rentals)}")
        rental = list(rentals.values())[0]
        print(f"  - {rental['name']} (Qty: {rental['qty']}, Days: {rental['daysRented']}, Total: ${rental['total']})\n")
    else:
        print("✗ No rentals found\n")
    
    # Test 7: Stock Management
    print("TEST 7: Stock - Verify Decremented")
    print("-" * 40)
    stock = r.hget('equipment:1', 'stock')
    if int(stock) < 5:  # Original was 5
        print(f"✓ Stock correctly decremented to {stock}\n")
    else:
        print(f"✗ Stock should be < 5, got {stock}\n")
    
    # Test 8: Add Second Rental (Same Equipment, Different Date)
    print("TEST 8: Rental - Add Duplicate Equipment")
    print("-" * 40)
    week_later = (datetime.now() + timedelta(days=8)).strftime('%Y-%m-%d')
    req = {
        'equipId': '1',
        'qty': '1',
        'returnDate': week_later
    }
    if addRental(req, '127.0.0.1'):
        print(f"✓ Added second rental: 1x Equipment #1 for {week_later}\n")
    else:
        print("✗ Failed to add second rental\n")
    
    # Test 9: Remove Rental
    print("TEST 9: Rental - Remove Equipment")
    print("-" * 40)
    updateRentals()
    if rentals:
        rentalId = list(rentals.keys())[0]
        req = {'rentalId': rentalId}
        if delRental(req, '127.0.0.1'):
            print(f"✓ Removed rental {rentalId}\n")
        else:
            print("✗ Failed to remove rental\n")
    else:
        print("✗ No rentals to remove\n")
    
    # Test 10: Stock Restored
    print("TEST 10: Stock - Verify Restored")
    print("-" * 40)
    stock = r.hget('equipment:1', 'stock')
    print(f"✓ Stock after return: {stock}\n")
    
    # Test 11: Admin Functions
    print("TEST 11: Admin - Add Admin")
    print("-" * 40)
    admin = True
    if addAdmin('sarah.smith@trailhire.com'):
        is_admin = r.sismember('admins', 'sarah.smith@trailhire.com')
        if is_admin:
            print(f"✓ User promoted to admin\n")
        else:
            print(f"✗ Admin promotion failed\n")
    else:
        print("✗ Failed to add admin\n")
    
    # Test 12: Signup
    print("TEST 12: Authentication - Signup")
    print("-" * 40)
    user = None  # Clear user for signup test
    req = {
        'email': 'test@example.com',
        'fname': 'Test',
        'password': 'TestPass123!',
        'sq': 'What is your pet\'s name?',
        'sa': 'Fluffy'
    }
    res, msg = signup(req, '127.0.0.1')
    if res:
        print(f"✓ New user registered: test@example.com\n")
    else:
        print(f"✗ Signup failed: {msg}\n")
    
    # Test 13: Duplicate Signup
    print("TEST 13: Authentication - Duplicate Email")
    print("-" * 40)
    res, msg = signup(req, '127.0.0.1')
    if not res:
        print(f"✓ Correctly rejected duplicate: {msg}\n")
    else:
        print(f"✗ Should reject duplicate email\n")
    
    # Summary
    print("="*60)
    print("✓ TEST SUITE COMPLETE")
    print("="*60 + "\n")

if __name__ == '__main__':
    
    # ! DELETES ALL KEYS !
    # wipeRedis()
    # loadDataFromCSV()
    
    # testSystem()
    
    app.run(debug=True)