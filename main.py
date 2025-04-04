import telebot
import sqlite3
from telebot.types import ForceReply
from flask import Flask
from threading import Thread
import cloudinary
import cloudinary.uploader
import cloudinary.api
from telebot.formatting import escape_markdown
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os

# ✅ Cấu hình bot
TOKEN = "7470737695:AAG1hWkTivI1DiWZOc_CzBrmb8nbsguJU-U"  # Thay bằng token của bạn
ADMIN_ID = 6283529520  # Thay bằng Telegram ID của admin (ví dụ: 6283529520)

# Tạo session với retry
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

bot = telebot.TeleBot(TOKEN, threaded=True)

# Cấu hình Cloudinary
cloudinary.config(
    cloud_name="dwwm2nkt4",
    api_key="339732977831829",
    api_secret="4YAAnZVCh4mKevUtS8fsqpr2p-k"
)

# Tạo Flask app để giữ bot chạy
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

def upload_to_cloudinary(local_file_path, cloudinary_path):
    try:
        response = cloudinary.uploader.upload(
            local_file_path,
            public_id=cloudinary_path,
            resource_type="raw",
            overwrite=True
        )
        print(f"✅ Đã upload {local_file_path} lên Cloudinary tại {cloudinary_path}")
    except Exception as e:
        print(f"❌ Lỗi khi upload lên Cloudinary: {str(e)}")

def download_from_cloudinary(cloudinary_path, local_file_path):
    try:
        url = cloudinary.api.resource(cloudinary_path, resource_type="raw")["url"]
        response = session.get(url, timeout=30)
        with open(local_file_path, "wb") as f:
            f.write(response.content)
        print(f"✅ Đã tải {cloudinary_path} từ Cloudinary về {local_file_path}")
    except Exception as e:
        print(f"❌ Lỗi khi tải từ Cloudinary: {str(e)}")

# Khởi tạo database
print("⏳ Khởi tạo database...")
if not os.path.exists("database.db"):
    try:
        print("⏳ Đang tải database từ Cloudinary...")
        download_from_cloudinary("database.db", "database.db")
        print("✅ Đã tải database từ Cloudinary")
    except Exception as e:
        print(f"❌ Lỗi khi tải database: {str(e)}")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                last_bill TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bypass_link TEXT UNIQUE,
                original_link TEXT,
                price REAL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("✅ Đã tạo database mới")
else:
    print("✅ File database.db đã tồn tại")

# Kết nối database
try:
    conn = sqlite3.connect("database.db", check_same_thread=False)
    cursor = conn.cursor()
    print("✅ Kết nối database thành công")
except Exception as e:
    print(f"❌ Lỗi khi kết nối database: {str(e)}")
    raise

# Kiểm tra bảng
try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone() is None:
        cursor.execute('''
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0,
                last_bill TEXT
            )
        ''')
        print("✅ Đã tạo bảng users")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='links'")
    if cursor.fetchone() is None:
        cursor.execute('''
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bypass_link TEXT UNIQUE,
                original_link TEXT,
                price REAL
            )
        ''')
        print("✅ Đã tạo bảng links")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'")
    if cursor.fetchone() is None:
        cursor.execute('''
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ Đã tạo bảng transactions")
    conn.commit()
except Exception as e:
    print(f"❌ Lỗi khi kiểm tra/tạo bảng: {str(e)}")
    raise

# Hàm tiện ích
def get_balance(user_id):
    try:
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"❌ Lỗi khi lấy số dư: {str(e)}")
        return 0

def update_balance(user_id, amount):
    try:
        cursor.execute(
            "INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
            (user_id, amount, amount))
        cursor.execute(
            "INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
            (user_id, amount, "deposit" if amount > 0 else "purchase"))
        conn.commit()
        upload_to_cloudinary("database.db", "database.db")
        print("✅ Đã cập nhật số dư")
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật số dư: {str(e)}")
        conn.rollback()

def add_link(bypass_link, original_link, price):
    try:
        cursor.execute(
            "INSERT INTO links (bypass_link, original_link, price) VALUES (?, ?, ?)",
            (bypass_link, original_link, price))
        conn.commit()
        upload_to_cloudinary("database.db", "database.db")
        return "✅ Link đã được thêm!"
    except sqlite3.IntegrityError:
        return "⚠️ Link này đã tồn tại!"
    except Exception as e:
        print(f"❌ Lỗi khi thêm link: {str(e)}")
        return "❌ Đã xảy ra lỗi!"

def get_link(bypass_link):
    try:
        cursor.execute("SELECT original_link, price FROM links WHERE bypass_link = ?", (bypass_link,))
        return cursor.fetchone()
    except Exception as e:
        print(f"❌ Lỗi khi lấy link: {str(e)}")
        return None

def format_currency(amount):
    return "{:,}".format(int(float(amount))).replace(",", ".")

# Lệnh /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.chat.id
    print(f"📌 Nhận lệnh /start từ user_id: {user_id}")
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
        conn.commit()
        print(f"✅ Đã thêm hoặc bỏ qua user_id {user_id} vào database")
    except Exception as e:
        print(f"❌ Lỗi khi thêm user_id {user_id} vào database: {str(e)}")
        return
    for attempt in range(5):
        try:
            bot.send_message(message.chat.id, "🤖 Chào mừng đến BOT mua link!\n💰 /nap_tien - Nạp tiền\n🔍 /so_du - Kiểm tra số dư\n🛒 /mua_link - Mua link", timeout=30)
            print(f"✅ Đã gửi tin nhắn chào mừng đến {user_id}")
            break
        except Exception as e:
            print(f"❌ Lỗi khi gửi tin nhắn /start (lần {attempt + 1}): {str(e)}")
            if attempt == 4:
                print("❌ Đã thử 5 lần nhưng vẫn thất bại.")
            time.sleep(2 ** attempt)

# Lệnh /so_du
@bot.message_handler(commands=["so_du"])
def check_balance(message):
    user_id = message.chat.id
    balance = get_balance(user_id)
    formatted_balance = format_currency(balance)
    bot.send_message(message.chat.id, f"💰 Số dư của bạn: {formatted_balance} VND")

# Lệnh /nap_tien
@bot.message_handler(commands=["nap_tien"])
def deposit_money(message):
    user_id = message.chat.id
    content = f"NAP{user_id}"
    qr_code_url = f"https://img.vietqr.io/image/ICB-109878256183-compact.png?amount=100000&addInfo={content}"
    msg_text = ("💵 Để nạp tiền, vui lòng chuyển khoản:\n"
                "🏦 *VIETTINBANK*\n📌 STK: `109878256183`\n👤 TTK: *CAO DINH TUAN ANH*\n"
                f"💬 Nội dung: `{content}`\n\n✅ NẠP TỐI THIỂU 10k\n✅ GỬI BILL ĐỂ XÁC NHẬN")
    bot.send_message(message.chat.id, msg_text, parse_mode="MarkdownV2")
    bot.send_photo(message.chat.id, qr_code_url, caption="📌 Quét QR để nạp nhanh!\n✅ GỬI BILL ĐỂ XÁC NHẬN")

# Xử lý ảnh bill
@bot.message_handler(content_types=["photo"])
def handle_bill_photo(message):
    user_id = message.chat.id
    file_id = message.photo[-1].file_id
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    cursor.execute("UPDATE users SET last_bill = ? WHERE user_id = ?", (file_id, user_id))
    conn.commit()
    bot.send_message(message.chat.id, "✅ Bill đã được lưu! Nhấn /XACNHAN để gửi.")

# Lệnh /XACNHAN
@bot.message_handler(commands=["XACNHAN"])
def confirm_deposit(message):
    user_id = message.chat.id
    cursor.execute("SELECT last_bill FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result or not result[0]:
        bot.send_message(message.chat.id, "❌ Bạn chưa gửi ảnh bill.")
        return
    bill_photo = result[0]
    bot.send_photo(ADMIN_ID, bill_photo, caption=f"🔔 *Xác nhận nạp tiền*\n👤 User ID: {user_id}\n- /confirm{user_id} : Xác nhận và cộng tiền\n- /deny{user_id} : Từ chối", parse_mode="Markdown")
    bot.send_message(message.chat.id, "✅ Bill đã gửi, chờ xác nhận.")

# Lệnh /confirm<user_id>
@bot.message_handler(regexp=r"^/confirm\d+$")
def handle_admin_confirm(message):
    print(f"Received command: {message.text}")
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền xác nhận.")
        return
    user_id = message.text.replace("/confirm", "")
    msg = bot.send_message(ADMIN_ID, f"💰 Nhập số tiền muốn cộng cho user {user_id}:", reply_markup=ForceReply())
    bot.register_next_step_handler(msg, process_add_money, user_id)

def process_add_money(message, user_id):
    print(f"Processing add money for user {user_id}, input: {message.text}")
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền thực hiện hành động này.")
        return
    try:
        amount = int(message.text)
        update_balance(int(user_id), amount)
        cursor.execute("UPDATE users SET last_bill = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        balance = get_balance(user_id)
        formatted_balance = format_currency(balance)
        bot.send_message(user_id, f"✅ Nạp tiền thành công! {amount:,} VND đã được cộng. Số dư: {formatted_balance} VND\n👉 /start")
        bot.send_message(ADMIN_ID, f"✔ Đã cộng {amount:,} VND cho user {user_id}")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Số tiền không hợp lệ. Nhập số nguyên.")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Lỗi: {str(e)}")

# Lệnh /deny<user_id>
@bot.message_handler(regexp=r"^/deny\d+$")
def handle_admin_deny(message):
    print(f"Received command: {message.text}")
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền từ chối.")
        return
    user_id = message.text.replace("/deny", "")
    cursor.execute("UPDATE users SET last_bill = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    upload_to_cloudinary("database.db", "database.db")
    bot.send_message(user_id, "❌ Yêu cầu nạp tiền đã bị từ chối.")
    bot.send_message(ADMIN_ID, f"✅ Đã từ chối yêu cầu của user {user_id}")

# Lệnh /mua_link
@bot.message_handler(commands=["mua_link"])
def mua_link_step1(message):
    bot.send_message(message.chat.id, "🔗 Nhập link vượt bạn muốn mua:")
    bot.register_next_step_handler(message, mua_link_step2)

def mua_link_step2(message):
    link_vuot = message.text
    user_id = message.chat.id
    link_data = get_link(link_vuot)
    if not link_data:
        bot.send_message(message.chat.id, "❌ Link không tồn tại.")
        return
    original_link, price = link_data
    balance = get_balance(user_id)
    if balance < price:
        shortfall = price - balance  # Tính số tiền còn thiếu
        formatted_price = format_currency(price)
        formatted_balance = format_currency(balance)
        formatted_shortfall = format_currency(shortfall)
        bot.send_message(message.chat.id, 
            f"❌ Số dư không đủ!\n"
            f"💵 Giá: {formatted_price} VND\n"
            f"💰 Số dư: {formatted_balance} VND\n"
            f"📉 Bạn cần nạp thêm: {formatted_shortfall} VND để đủ tiền mua link này."
        )
        return
    update_balance(user_id, -price)
    bot.send_message(message.chat.id, f"🎉 Mua thành công!\n🔗 Link: {original_link}\n💰 Số dư còn lại: {format_currency(get_balance(user_id))} VND")

# Lệnh /admin
@bot.message_handler(commands=["admin"])
def admin_menu(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền truy cập.")
        return
    bot.send_message(message.chat.id, "👨‍💻 **Menu Admin**\n- /add_link : Thêm link\n- /delete_link : Xóa link\n- /list_users : Danh sách người dùng\n- /list_links : Danh sách link\n- /adjust_balance : Điều chỉnh số dư\n- /announcement : Gửi thông báo")

# Lệnh /add_link
@bot.message_handler(commands=["add_link"])
def admin_add_link_step1(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    msg = bot.send_message(ADMIN_ID, "🔗 Nhập link vượt:")
    bot.register_next_step_handler(msg, admin_add_link_step2)

def admin_add_link_step2(message):
    bypass_link = message.text
    msg = bot.send_message(ADMIN_ID, "🔗 Nhập link gốc:")
    bot.register_next_step_handler(msg, admin_add_link_step3, bypass_link)

def admin_add_link_step3(message, bypass_link):
    original_link = message.text
    msg = bot.send_message(ADMIN_ID, "💰 Nhập giá (VND):")
    bot.register_next_step_handler(msg, admin_add_link_step4, bypass_link, original_link)

def admin_add_link_step4(message, bypass_link, original_link):
    try:
        price = int(message.text)
        result = add_link(bypass_link, original_link, price)
        bot.send_message(ADMIN_ID, result)
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Giá phải là số nguyên.")

# Lệnh /delete_link
@bot.message_handler(commands=["delete_link"])
def admin_delete_link(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    msg = bot.send_message(ADMIN_ID, "🔗 Nhập link vượt cần xóa:")
    bot.register_next_step_handler(msg, process_delete_link)

def process_delete_link(message):
    bypass_link = message.text
    cursor.execute("DELETE FROM links WHERE bypass_link = ?", (bypass_link,))
    conn.commit()
    if cursor.rowcount > 0:
        upload_to_cloudinary("database.db", "database.db")
        bot.send_message(message.chat.id, f"✅ Đã xóa link: {bypass_link}")
    else:
        bot.send_message(message.chat.id, "❌ Link không tồn tại.")

# Lệnh /list_users
@bot.message_handler(commands=["list_users"])
def list_users(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    cursor.execute("SELECT user_id, balance FROM users")
    users = cursor.fetchall()
    if not users:
        bot.send_message(message.chat.id, "❌ Không có người dùng.")
        return
    user_list = "👥 *Danh sách người dùng:*\n"
    for user_id, balance in users:
        user_list += f"- ID: `{user_id}`, Số dư: `{format_currency(balance)} VND`\n"
    bot.send_message(message.chat.id, user_list, parse_mode="Markdown")

# Lệnh /list_links
@bot.message_handler(commands=["list_links"])
def list_links(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    cursor.execute("SELECT bypass_link, original_link, price FROM links")
    links = cursor.fetchall()
    if not links:
        bot.send_message(message.chat.id, "❌ Không có link.")
        return
    link_list = "🔗 *Danh sách link:*\n"
    for idx, (bypass_link, original_link, price) in enumerate(links, 1):
        link_list += (f"{idx}. **Link vượt**: `{escape_markdown(bypass_link)}`\n"
                      f"   **Link gốc**: `{escape_markdown(original_link)}`\n"
                      f"   **Giá**: `{format_currency(price)} VND`\n\n")
    bot.send_message(message.chat.id, link_list, parse_mode="Markdown")

# Lệnh /adjust_balance
@bot.message_handler(commands=["adjust_balance"])
def admin_adjust_balance_step1(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    msg = bot.send_message(ADMIN_ID, "👤 Nhập ID người dùng:")
    bot.register_next_step_handler(msg, admin_adjust_balance_step2)

def admin_adjust_balance_step2(message):
    user_id = message.text
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, "❌ Người dùng không tồn tại.")
        return
    msg = bot.send_message(ADMIN_ID, "💰 Nhập số tiền (dương để cộng, âm để trừ):")
    bot.register_next_step_handler(msg, admin_adjust_balance_step3, user_id)

def admin_adjust_balance_step3(message, user_id):
    try:
        amount = int(message.text)
        update_balance(int(user_id), amount)
        bot.send_message(ADMIN_ID, f"✅ Đã điều chỉnh số dư cho user {user_id}. Số dư mới: {format_currency(get_balance(user_id))} VND")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Số tiền không hợp lệ.")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Lỗi: {str(e)}")

# Lệnh /announcement
@bot.message_handler(commands=["announcement"])
def admin_announcement(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền.")
        return
    msg = bot.send_message(ADMIN_ID, "📢 Nhập nội dung thông báo:")
    bot.register_next_step_handler(msg, process_announcement)

def process_announcement(message):
    content = message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    if not users:
        bot.send_message(ADMIN_ID, "❌ Không có người dùng để gửi thông báo.")
        return
    success_count = 0
    for (user_id,) in users:
        try:
            bot.send_message(user_id, f"📢 *Thông báo từ Admin:*\n{content}", parse_mode="Markdown")
            success_count += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"✅ Đã gửi thông báo đến {success_count} người dùng.")

# Giữ bot chạy
def keep_alive():
    t = Thread(target=run)
    t.start()

# Khởi động bot
if __name__ == "__main__":
    print("Bot is starting...")
    keep_alive()
    bot.polling(none_stop=True, interval=0, timeout=30)