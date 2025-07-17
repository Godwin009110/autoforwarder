from flask import Flask, render_template, request, jsonify, redirect, session
import os
from dotenv import load_dotenv
import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import json
import re
import time
from datetime import datetime, timedelta
from telethon.errors import UsernameNotOccupiedError, UsernameOccupiedError
from telethon.tl.functions.channels import CreateChannelRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.functions.account import UpdateUsernameRequest
import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Create a function to run async code in Flask
def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def get_fragment_auction_details(username):
    """Fetch auction details from Fragment.com"""
    try:
        url = f"https://fragment.com/username/{username}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Initialize auction details
        auction_details = {
            'available': False,
            'minimum_bid': None,
            'current_price': None,
            'usd_price': None,
            'decreases_by': None,
            'minimum_price': None,
            'status': 'Unknown',
            'fragment_url': url
        }
        
        # Check if username is available on Fragment
        if 'Available' in response.text:
            auction_details['available'] = True
            auction_details['status'] = 'Available for Auction'
            
            # Extract minimum bid information
            bid_pattern = r'Minimum Bid[^0-9]*(\d+)[^$]*\$([0-9,]+)'
            bid_match = re.search(bid_pattern, response.text)
            if bid_match:
                auction_details['minimum_bid'] = int(bid_match.group(1))
                auction_details['usd_price'] = bid_match.group(2).replace(',', '')
            
            # Extract decrease information
            decrease_pattern = r'Decreases by (\d+) every day.*?minimum price of (\d+)'
            decrease_match = re.search(decrease_pattern, response.text)
            if decrease_match:
                auction_details['decreases_by'] = int(decrease_match.group(1))
                auction_details['minimum_price'] = int(decrease_match.group(2))
        
        elif 'Sold' in response.text or 'Owner' in response.text:
            auction_details['status'] = 'Sold'
            
            # Try to extract sold price
            sold_pattern = r'Sold for[^0-9]*(\d+)[^$]*\$([0-9,]+)'
            sold_match = re.search(sold_pattern, response.text)
            if sold_match:
                auction_details['sold_price'] = int(sold_match.group(1))
                auction_details['sold_usd'] = sold_match.group(2).replace(',', '')
        
        elif 'Auction' in response.text:
            auction_details['status'] = 'Active Auction'
            
            # Extract current bid information
            current_pattern = r'Current bid[^0-9]*(\d+)[^$]*\$([0-9,]+)'
            current_match = re.search(current_pattern, response.text)
            if current_match:
                auction_details['current_price'] = int(current_match.group(1))
                auction_details['usd_price'] = current_match.group(2).replace(',', '')
        
        return auction_details
        
    except requests.RequestException as e:
        logger.error(f"Error fetching Fragment data for {username}: {e}")
        return {
            'available': False,
            'status': 'Fragment Error',
            'error': str(e),
            'fragment_url': f"https://fragment.com/username/{username}"
        }
    except Exception as e:
        logger.error(f"Error parsing Fragment data for {username}: {e}")
        return {
            'available': False,
            'status': 'Parse Error',
            'error': str(e),
            'fragment_url': f"https://fragment.com/username/{username}"
        }
        
@app.route('/')
def ping():
    return 'pong'

@app.route('/login')
def index():
    user_id = request.args.get('user_id', '')
    first_name = request.args.get('first_name', '')
    
    # Store in session for later use
    session['user_id'] = user_id
    session['first_name'] = first_name
    
    return render_template('index.html', user_id=user_id, first_name=first_name)

@app.route('/submit-phone', methods=['POST'])
def submit_phone():
    """Handle phone number submission"""
    phone = request.form.get('phone')
    user_id = request.form.get('user_id', '')
    
    print(f"Received phone: {phone}")
    print(f"Received user_id: {user_id}")

    if not phone:
        print("Error: Phone number is missing")
        return jsonify({'success': False, 'message': 'Phone number is required'})
    
    import re
    if not re.match(r'^\+[1-9]\d{1,14}$', phone):
        return jsonify({'success': False, 'message': 'Phone number must be in international format (e.g., +1234567890)'})
    
    # Load user data to get API credentials
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        
        print(f"Config loaded successfully")

        user_data = data["users"].get(user_id, {})
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        forwarding_on = user_data.get("forwarding_on", False)
        auto_reply_status = user_data.get("auto_reply_status", False)
        
        # Define message variable with a default value
        message = "You are already logged in"
        
        if forwarding_on and auto_reply_status:
            message = "You are already logged in with forwarding and auto-reply enabled"
        elif forwarding_on:
            message = "You are already logged in with forwarding enabled"
        elif auto_reply_status:
            message = "You are already logged in with auto-reply enabled"
                
        # Check if session exists
        session_file = f'{user_id}.session'
        if os.path.exists(session_file):
            # Verify if the session is valid
            async def check_session():
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if await client.is_user_authorized():
                    await client.disconnect()
                    return True
                
                await client.disconnect()
                return False
            
            is_authorized = run_async(check_session())
            if is_authorized:
                # User already has a valid session
                return jsonify({
                    'success': True, 
                    'already_logged_in': True, 
                    'message': message,
                    'forwarding_on': forwarding_on,
                    'auto_reply_status': auto_reply_status
                })
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'message': 'API credentials not found. Please set them first.'})
        
        # Store in session for later use
        session['user_id'] = user_id
        session['phone'] = phone
        session['api_id'] = api_id
        session['api_hash'] = api_hash
        
        # Create a new Telethon client and send code request
        async def send_code():
            # Create sessions directory if it doesn't exist
            os.makedirs('sessions', exist_ok=True)
            
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Send the code request
            sent_code = await client.send_code_request(phone)
            session['phone_code_hash'] = sent_code.phone_code_hash
            
            await client.disconnect()
            return True
        
        success = run_async(send_code())
        if success:
            return jsonify({'success': True, 'phone': phone})
        else:
            return jsonify({'success': False, 'message': 'Failed to send verification code'})
        
    except Exception as e:
        logger.error(f"Error in submit-phone: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/submit-otp', methods=['POST'])
def submit_otp():
    """Handle OTP submission"""
    otp = request.form.get('otp')
    phone = request.form.get('phone')
    
    if not otp or not phone:
        return jsonify({'success': False, 'message': 'OTP and phone are required'})
    
    user_id = session.get('user_id')
    api_id = session.get('api_id')
    api_hash = session.get('api_hash')
    phone_code_hash = session.get('phone_code_hash')
    
    if not all([user_id, api_id, api_hash, phone_code_hash]):
        return jsonify({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_code():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            try:
                # Try to sign in with the code
                await client.sign_in(phone=phone, code=otp, phone_code_hash=phone_code_hash)
                await client.disconnect()
                
                # Copy the session file to the main directory
                import shutil
                source_path = f'sessions/{user_id}.session'
                target_path = f'{user_id}.session'
                shutil.copy2(source_path, target_path)
                
                return {'success': True, 'needs_2fa': False}
                
            except SessionPasswordNeededError:
                await client.disconnect()
                return {'success': True, 'needs_2fa': True}
                
        except Exception as e:
            logger.error(f"Error in verify_code: {e}")
            return {'success': False, 'message': str(e)}
    
    result = run_async(verify_code())
    return jsonify(result)

@app.route('/submit-2fa', methods=['POST'])
def submit_2fa():
    """Handle 2FA password submission"""
    password = request.form.get('password')
    
    if not password:
        return jsonify({'success': False, 'message': 'Password is required'})
    
    user_id = session.get('user_id')
    api_id = session.get('api_id')
    api_hash = session.get('api_hash')
    
    if not all([user_id, api_id, api_hash]):
        return jsonify({'success': False, 'message': 'Session data missing. Please start over.'})
    
    async def verify_2fa():
        try:
            # Create a new Telethon client
            client = TelegramClient(f'sessions/{user_id}.session', api_id, api_hash)
            await client.connect()
            
            # Sign in with 2FA password
            await client.sign_in(password=password)
            await client.disconnect()
            
            # Copy the session file to the main directory
            import shutil
            source_path = f'sessions/{user_id}.session'
            target_path = f'{user_id}.session'
            shutil.copy2(source_path, target_path)
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"Error in verify_2fa: {e}")
            return {'success': False, 'message': str(e)}
    
    result = run_async(verify_2fa())
    return jsonify(result)

@app.route('/save-api-credentials', methods=['POST'])
def save_api_credentials():
    """Handle API credentials submission"""
    try:
        data = request.json
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        user_id = data.get('user_id')
        
        if not all([api_id, api_hash, user_id]):
            return jsonify({'success': False, 'message': 'API ID, API Hash, and User ID are required'})
        
        # Load config file
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            config_data = {"users": {}}
        
        # Ensure users dict exists
        if "users" not in config_data:
            config_data["users"] = {}
        
        # Ensure user exists in config
        if user_id not in config_data["users"]:
            config_data["users"][user_id] = {}
        
        # Update API credentials
        config_data["users"][user_id]["api_id"] = api_id
        config_data["users"][user_id]["api_hash"] = api_hash
        
        # Save updated config
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=4)
        
        return jsonify({'success': True, 'message': 'API credentials saved successfully'})
        
    except Exception as e:
        logger.error(f"Error in save-api-credentials: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/success')
def success():
    """Show success page after login"""
    return render_template('success.html')

@app.route('/username')
def username_checker():
    user_id = request.args.get('user_id', '')
    first_name = request.args.get('first_name', '')
    
    # Get usage count and reset time
    usage_count, reset_time = get_usage_info(user_id)
    
    return render_template('username.html', 
                         user_id=user_id, 
                         first_name=first_name,
                         usage_count=usage_count,
                         reset_time=reset_time)

def get_usage_info(user_id):
    """Get current usage count and reset time for user"""
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        
        user_data = data["users"].get(user_id, {})
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Initialize usage tracking if not exists
        if "username_usage" not in user_data:
            user_data["username_usage"] = {"date": today, "count": 0}
        
        # Reset count if it's a new day
        if user_data["username_usage"]["date"] != today:
            user_data["username_usage"] = {"date": today, "count": 0}
            
            # Save updated data
            data["users"][user_id] = user_data
            with open("config.json", "w") as f:
                json.dump(data, f, indent=4)
        
        usage_count = user_data["username_usage"]["count"]
        
        # Calculate reset time (next day at midnight)
        tomorrow = datetime.now() + timedelta(days=1)
        reset_time = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
        time_diff = reset_time - datetime.now()
        
        hours = int(time_diff.total_seconds() // 3600)
        minutes = int((time_diff.total_seconds() % 3600) // 60)
        
        reset_time_str = f"{hours}h {minutes}m"
        
        return usage_count, reset_time_str
        
    except Exception as e:
        logger.error(f"Error getting usage info: {e}")
        return 0, "24h 0m"

def increment_usage_count(user_id):
    """Increment usage count for user"""
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
        
        user_data = data["users"].get(user_id, {})
        today = datetime.now().strftime("%Y-%m-%d")
        
        if "username_usage" not in user_data:
            user_data["username_usage"] = {"date": today, "count": 0}
        
        if user_data["username_usage"]["date"] != today:
            user_data["username_usage"] = {"date": today, "count": 0}
        
        user_data["username_usage"]["count"] += 1
        
        data["users"][user_id] = user_data
        with open("config.json", "w") as f:
            json.dump(data, f, indent=4)
            
        return user_data["username_usage"]["count"]
        
    except Exception as e:
        logger.error(f"Error incrementing usage count: {e}")
        return 0

def analyze_username(username):
    """Enhanced username analysis with better valuation algorithm"""
    length = len(username)
    
    # Premium usernames database (examples of high-value usernames)
    premium_usernames = {
        'minted': 500.0,
        'crypto': 800.0,
        'bitcoin': 1000.0,
        'ethereum': 750.0,
        'nft': 600.0,
        'defi': 400.0,
        'web3': 350.0,
        'metaverse': 300.0,
        'ai': 900.0,
        'tech': 450.0,
        'money': 550.0,
        'gold': 400.0,
        'diamond': 350.0,
        'luxury': 300.0,
        'premium': 250.0,
        'vip': 200.0,
        'pro': 150.0,
        'official': 180.0,
        'news': 220.0,
        'media': 200.0,
        'finance': 300.0,
        'trading': 280.0,
        'invest': 250.0,
        'market': 200.0,
        'business': 180.0,
        'startup': 150.0,
        'innovation': 120.0,
        'future': 100.0,
        'digital': 90.0,
        'online': 80.0,
        'global': 120.0,
        'world': 100.0,
        'international': 80.0,
        'network': 70.0,
        'system': 60.0,
        'platform': 50.0,
        'service': 40.0,
        'solution': 35.0,
        'app': 80.0,
        'mobile': 60.0,
        'smart': 70.0,
        'cloud': 90.0,
        'data': 85.0,
        'security': 95.0,
        'privacy': 75.0,
        'blockchain': 200.0,
        'token': 150.0,
        'coin': 120.0,
        'wallet': 100.0,
        'exchange': 180.0,
        'bank': 250.0,
        'pay': 200.0,
        'payment': 150.0,
        'transfer': 80.0,
        'send': 60.0,
        'receive': 50.0,
        'buy': 70.0,
        'sell': 65.0,
        'trade': 90.0,
        'shop': 85.0,
        'store': 80.0,
        'market': 100.0,
        'sale': 60.0,
        'deal': 55.0,
        'offer': 50.0,
        'discount': 45.0,
        'free': 40.0,
        'premium': 120.0,
        'plus': 60.0,
        'max': 55.0,
        'ultra': 50.0,
        'super': 45.0,
        'mega': 40.0,
        'best': 70.0,
        'top': 75.0,
        'first': 65.0,
        'new': 50.0,
        'latest': 45.0,
        'update': 40.0,
        'version': 35.0,
        'beta': 30.0,
        'alpha': 25.0,
        'test': 20.0,
        'demo': 18.0,
        'trial': 15.0,
        'sample': 12.0,
        'example': 10.0
    }
    
    # Check if username is in premium list
    username_lower = username.lower()
    if username_lower in premium_usernames:
        base_value = premium_usernames[username_lower]
        rarity = "Legendary" if base_value >= 500 else "Epic" if base_value >= 200 else "Rare" if base_value >= 100 else "Uncommon"
        confidence = 98
    else:
        # Base valuation by length
        if length <= 2:
            rarity = "Mythical"
            base_value = 1000.0
            confidence = 99
        elif length == 3:
            rarity = "Legendary"
            base_value = 200.0
            confidence = 95
        elif length == 4:
            rarity = "Epic"
            base_value = 80.0
            confidence = 90
        elif length == 5:
            rarity = "Rare"
            base_value = 35.0
            confidence = 85
        elif length == 6:
            rarity = "Uncommon"
            base_value = 15.0
            confidence = 80
        elif length <= 8:
            rarity = "Common"
            base_value = 8.0
            confidence = 75
        else:
            rarity = "Basic"
            base_value = 3.0
            confidence = 70
    
    # Pattern bonuses
    if re.match(r'^\d+$', username):  # Pure numbers
        if length <= 4:
            base_value *= 3.0
            confidence += 10
        elif length <= 6:
            base_value *= 2.0
            confidence += 5
        else:
            base_value *= 1.5
    
    elif re.match(r'^[a-zA-Z]+$', username):  # Pure letters
        if length <= 5:
            base_value *= 2.5
            confidence += 8
        else:
            base_value *= 1.8
            confidence += 5
    
    elif re.match(r'^[a-z]+$', username):  # Lowercase only
        base_value *= 1.5
        confidence += 3
    
    elif re.match(r'^[A-Z]+$', username):  # Uppercase only
        base_value *= 1.3
        confidence += 2
    
    # Special character penalties
    if '_' in username:
        base_value *= 0.7
        confidence -= 8
    
    if username.count('_') > 1:
        base_value *= 0.5
        confidence -= 15
    
    # Dictionary word bonus
    common_english_words = [
        'love', 'life', 'time', 'world', 'home', 'work', 'play', 'game', 'book', 'music',
        'art', 'food', 'travel', 'photo', 'video', 'film', 'movie', 'show', 'news', 'sport',
        'car', 'bike', 'run', 'walk', 'dance', 'sing', 'read', 'write', 'learn', 'teach',
        'help', 'care', 'heal', 'grow', 'build', 'make', 'create', 'design', 'style', 'fashion',
        'beauty', 'health', 'fit', 'strong', 'fast', 'quick', 'easy', 'simple', 'clean', 'fresh'
    ]
    
    if username_lower in common_english_words:
        base_value *= 1.8
        confidence += 10
    
    # Repetitive patterns penalty
    if len(set(username)) < len(username) * 0.6:  # Too many repeated characters
        base_value *= 0.6
        confidence -= 12
    
    # Sequential patterns bonus/penalty
    if re.match(r'^(abc|123|xyz|789).*', username_lower):
        base_value *= 1.2
        confidence += 5
    
    # Brand/company name patterns
    tech_brands = ['apple', 'google', 'meta', 'tesla', 'amazon', 'microsoft', 'netflix', 'uber', 'airbnb']
    if any(brand in username_lower for brand in tech_brands):
        base_value *= 0.3  # Trademark issues
        confidence -= 20
    
    # Ensure minimum values
    base_value = max(1.0, base_value)
    confidence = max(60, min(99, confidence))
    
    # Adjust rarity based on final value
    if base_value >= 500:
        rarity = "Mythical"
    elif base_value >= 200:
        rarity = "Legendary"
    elif base_value >= 100:
        rarity = "Epic"
    elif base_value >= 50:
        rarity = "Rare"
    elif base_value >= 20:
        rarity = "Uncommon"
    elif base_value >= 10:
        rarity = "Common"
    else:
        rarity = "Basic"
    
    return {
        "rarity": rarity,
        "value": round(base_value, 1),
        "confidence": confidence
    }

@app.route('/check-username', methods=['POST'])
def check_username():
    """Check username availability and analyze it"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        user_id = data.get('user_id', '')
        
        if not username or not user_id:
            return jsonify({'success': False, 'message': 'Username and user ID are required'})
        
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_]{4,32}$', username):
            return jsonify({'success': False, 'message': 'Invalid username format. Must be 4-32 characters, letters, numbers, and underscores only.'})
        
        # Check if user exists in config
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        user_data = config_data["users"].get(user_id, {})
        if not user_data:
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        # Check usage limits (skip for admins)
        if user_id not in ADMIN_IDS:
            usage_count, _ = get_usage_info(user_id)
            if usage_count >= 3:
                return jsonify({'success': False, 'message': 'Daily usage limit reached (3/3). Try again tomorrow.'})
        
        # Check if auto-reply or forwarding is enabled
        if user_data.get('auto_reply_status', False) or user_data.get('forwarding_on', False):
            return jsonify({'success': False, 'message': 'Please disable auto-reply and forwarding before using username checker'})
        
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'message': 'API credentials not found. Please set them first.'})
        
        # Check if session exists
        session_file = f'{user_id}.session'
        if not os.path.exists(session_file):
            return jsonify({
                'success': False, 
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Please login first'
            })
        
        # Verify session is valid before proceeding
        async def verify_session():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return False
                
                await client.disconnect()
                return True
                
            except Exception as e:
                logger.error(f"Error verifying session: {e}")
                return False
        
        is_session_valid = run_async(verify_session())
        
        if not is_session_valid:
            return jsonify({
                'success': False,
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Session expired. Please login again.'
            })
        
        # Check username availability
        async def check_availability():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return {'success': False, 'message': 'Session expired. Please login again.'}
                
                try:
                    # Try to get entity with the username
                    entity = await client.get_entity(username)
                    await client.disconnect()
                    return {'available': False}  # Username is taken
                except (UsernameNotOccupiedError, ValueError) as e:
                    await client.disconnect()
                    
                    # Check if this is the specific error indicating Fragment auction
                    error_msg = str(e)
                    if "Nobody is using this username, or the username is unacceptable" in error_msg or "ResolveUsernameRequest" in error_msg:
                        # This username might be on Fragment auction
                        logger.info(f"Username {username} might be on Fragment auction, checking...")
                        fragment_details = get_fragment_auction_details(username)
                        return {
                            'available': False,
                            'fragment_auction': True,
                            'fragment_details': fragment_details
                        }
                    else:
                        return {'available': True}  # Username is available
                except Exception as e:
                    await client.disconnect()
                    logger.error(f"Error checking username: {e}")
                    
                    # Check if this might be a Fragment auction case
                    error_msg = str(e)
                    if "Nobody is using this username" in error_msg or "unacceptable" in error_msg:
                        logger.info(f"Username {username} might be on Fragment auction due to error: {error_msg}")
                        fragment_details = get_fragment_auction_details(username)
                        return {
                            'available': False,
                            'fragment_auction': True,
                            'fragment_details': fragment_details
                        }
                    
                    return {'available': False}  # Assume taken on error
                    
            except Exception as e:
                logger.error(f"Error in check_availability: {e}")
                return {'success': False, 'message': f'Error checking username: {str(e)}'}
        
        result = run_async(check_availability())
        
        if 'success' in result and not result['success']:
            return jsonify(result)
        
        # Increment usage count (skip for admins)
        new_usage_count = 0
        if user_id not in ADMIN_IDS:
            new_usage_count = increment_usage_count(user_id)
        
        # Analyze username with enhanced algorithm
        analysis = analyze_username(username)
        
        return jsonify({
            'success': True,
            'available': result.get('available', False),
            'fragment_auction': result.get('fragment_auction', False),
            'fragment_details': result.get('fragment_details', {}),
            'analysis': analysis,
            'usage_count': new_usage_count
        })
        
    except Exception as e:
        logger.error(f"Error in check-username: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/create-channel', methods=['POST'])
def create_channel():
    """Create a Telegram channel with the specified username"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        user_id = data.get('user_id', '')
        
        if not username or not user_id:
            return jsonify({'success': False, 'message': 'Username and user ID are required'})
        
        # Get user data
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        user_data = config_data["users"].get(user_id, {})
        if not user_data:
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        if user_data.get('auto_reply_status', False) or user_data.get('forwarding_on', False):
            return jsonify({'success': False, 'message': 'Please disable auto-reply and forwarding before using username checker'})
        
        # Get API credentials
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'message': 'API credentials not found'})
        
        # Check session
        session_file = f'{user_id}.session'
        if not os.path.exists(session_file):
            return jsonify({
                'success': False,
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Please login first'
            })
        
        # Verify session is valid before proceeding
        async def verify_session():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return False
                
                await client.disconnect()
                return True
                
            except Exception as e:
                logger.error(f"Error verifying session: {e}")
                return False
        
        is_session_valid = run_async(verify_session())
        
        if not is_session_valid:
            return jsonify({
                'success': False,
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Session expired. Please login again.'
            })
        
        # Create channel
        async def create_telegram_channel():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return {'success': False, 'message': 'Session expired. Please login again.'}
                
                # Create the channel
                result = await client(CreateChannelRequest(
                    title=username,
                    about=f"Channel created via FluX𝕏♛ ADSBOT",
                    megagroup=False
                ))
                
                channel = result.chats[0]
                
                # Set username
                try:
                    await client(UpdateUsernameRequest(
                        channel=channel,
                        username=username
                    ))
                except Exception as e:
                    logger.error(f"Error setting username: {e}")
                    # Continue even if username setting fails
                
                # Try to set profile photo (user's profile photo)
                try:
                    me = await client.get_me()
                    if me.photo:
                        # Get user's profile photos
                        photos = await client.get_profile_photos('me', limit=1)
                        if photos:
                            # Download the photo
                            photo_path = f'temp_photo_{user_id}.jpg'
                            await client.download_media(photos[0], photo_path)
                            
                            # Upload as channel photo
                            await client(UploadProfilePhotoRequest(
                                file=await client.upload_file(photo_path)
                            ))
                            
                            # Clean up temp file
                            if os.path.exists(photo_path):
                                os.remove(photo_path)
                except Exception as e:
                    logger.error(f"Error setting channel photo: {e}")
                    # Continue even if photo setting fails
                
                await client.disconnect()
                
                channel_link = f"https://t.me/{username}"
                
                return {
                    'success': True,
                    'channel_link': channel_link,
                    'channel_id': channel.id
                }
                
            except UsernameOccupiedError:
                await client.disconnect()
                return {'success': False, 'message': 'Username is already taken'}
            except Exception as e:
                await client.disconnect()
                logger.error(f"Error creating channel: {e}")
                return {'success': False, 'message': f'Error creating channel: {str(e)}'}
        
        result = run_async(create_telegram_channel())
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in create-channel: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/set-username', methods=['POST'])
def set_username():
    """Set username for the user's Telegram account"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        user_id = data.get('user_id', '')
        
        if not username or not user_id:
            return jsonify({'success': False, 'message': 'Username and user ID are required'})
        
        # Validate username format
        if not re.match(r'^[a-zA-Z0-9_]{4,32}$', username):
            return jsonify({'success': False, 'message': 'Invalid username format'})
        
        # Get user data
        try:
            with open("config.json", "r") as f:
                config_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        user_data = config_data["users"].get(user_id, {})
        if not user_data:
            return jsonify({'success': False, 'message': 'User not found in system'})
        
        # Check if auto-reply or forwarding is enabled
        if user_data.get('auto_reply_status', False) or user_data.get('forwarding_on', False):
            return jsonify({'success': False, 'message': 'Please disable auto-reply and forwarding before setting username'})
        
        # Get API credentials
        api_id = user_data.get("api_id")
        api_hash = user_data.get("api_hash")
        
        if not api_id or not api_hash:
            return jsonify({'success': False, 'message': 'API credentials not found'})
        
        # Check session
        session_file = f'{user_id}.session'
        if not os.path.exists(session_file):
            return jsonify({
                'success': False,
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Please login first'
            })
        
        # Verify session is valid before proceeding
        async def verify_session():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return False
                
                await client.disconnect()
                return True
                
            except Exception as e:
                logger.error(f"Error verifying session: {e}")
                return False
        
        is_session_valid = run_async(verify_session())
        
        if not is_session_valid:
            return jsonify({
                'success': False,
                'redirect': True,
                'redirect_url': f'/login?user_id={user_id}',
                'message': 'Session expired. Please login again.'
            })
        
        # Set username
        async def set_user_username():
            try:
                client = TelegramClient(session_file, api_id, api_hash)
                await client.connect()
                
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return {'success': False, 'message': 'Session expired. Please login again.'}
                
                # First check if username is still available
                try:
                    entity = await client.get_entity(username)
                    await client.disconnect()
                    return {'success': False, 'message': 'Username is no longer available'}
                except (UsernameNotOccupiedError, ValueError):
                    # Username is available, proceed
                    pass
                except Exception as e:
                    await client.disconnect()
                    logger.error(f"Error checking username availability: {e}")
                    return {'success': False, 'message': 'Error checking username availability'}
                
                # Set the username for the user account
                from telethon.tl.functions.account import UpdateUsernameRequest
                
                try:
                    await client(UpdateUsernameRequest(username=username))
                    await client.disconnect()
                    
                    return {
                        'success': True,
                        'message': f'Username @{username} has been set successfully'
                    }
                    
                except UsernameOccupiedError:
                    await client.disconnect()
                    return {'success': False, 'message': 'Username is already taken'}
                except Exception as e:
                    await client.disconnect()
                    logger.error(f"Error setting username: {e}")
                    return {'success': False, 'message': f'Error setting username: {str(e)}'}
                    
            except Exception as e:
                logger.error(f"Error in set_user_username: {e}")
                return {'success': False, 'message': f'Error: {str(e)}'}
        
        result = run_async(set_user_username())
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in set-username: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

def start_flask_app():
    """Start the Flask app in a separate thread"""
    # Create sessions directory if it doesn't exist
    os.makedirs('sessions', exist_ok=True)
    
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5000))
    
    # Start Flask app
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)

# This allows the Flask app to be imported and started from main.py
if __name__ == '__main__':
    start_flask_app()
