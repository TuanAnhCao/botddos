import telebot
import json
import sqlite3
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from flask import Flask
from threading import Thread
import telebot.util
from telebot.formatting import escape_markdown  # Import hàm escape_markdown

# ✅ Cấu hình bot
TOKEN = "7470737695:AAG1hWkTivI1DiWZOc_CzBrmb8nbsguJU-U"
ADMIN_ID = 6283529520  # Thay bằng Telegram ID của admin

bot = telebot.TeleBot(TOKEN)

# Kết nối database
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# Tạo bảng nếu chưa có
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

# Hàm lấy số dư
def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0


# Hàm cập nhật số dư
def update_balance(user_id, amount):
    cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
                   (user_id, amount, amount))
    cursor.execute("INSERT INTO transactions (user_id, amount, type) VALUES (?, ?, ?)",
                   (user_id, amount, "deposit" if amount > 0 else "purchase"))
    conn.commit()


# Hàm thêm link vào DB (Admin)
def add_link(bypass_link, original_link, price):
    try:
        cursor.execute("INSERT INTO links (bypass_link, original_link, price) VALUES (?, ?, ?)",
                       (bypass_link, original_link, price))
        conn.commit()
        return "✅ Link đã được thêm!"
    except sqlite3.IntegrityError:
        return "⚠️ Link này đã tồn tại!"


# Hàm lấy giá và link gốc
def get_link(bypass_link):
    cursor.execute("SELECT original_link, price FROM links WHERE bypass_link = ?", (bypass_link,))
    return cursor.fetchone()

# Định dạng số tiền
def format_currency(amount):
    return "{:,}".format(int(float(amount))).replace(",", ".")


# Database helper functions
def get_user_balance(telegram_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return f"{int(result[0]):,} VNĐ".replace(",", ".")
    return None

def set_user_balance(user_id, balance):
    cursor.execute("INSERT OR REPLACE INTO users (user_id, balance) VALUES (?, ?)", (user_id, balance))
    conn.commit()

def get_link_info(bypass_link):
    cursor.execute("SELECT original_link, price FROM links WHERE bypass_link = ?", (bypass_link,))
    result = cursor.fetchone()
    return {"url": result[0], "price": result[1]} if result else None

def save_link(bypass_link, original_link, price):
    cursor.execute("INSERT OR REPLACE INTO links (bypass_link, original_link, price) VALUES (?, ?, ?)", 
                  (bypass_link, original_link, price))
    conn.commit()


#Thêm TB
@bot.message_handler(commands=["thong_bao"])
def send_announcement(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền sử dụng lệnh này.")
        return

    msg = bot.send_message(ADMIN_ID, "📢 Nhập nội dung thông báo:")
    bot.register_next_step_handler(msg, process_announcement)

def process_announcement(message):
    content = message.text
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()

    if not users:
        bot.send_message(ADMIN_ID, "❌ Không có người dùng nào để gửi thông báo.")
        return

    success_count = 0
    for (user_id,) in users:
        try:
            bot.send_message(user_id, f"📢 *Thông báo từ Admin:*\n{content}", parse_mode="Markdown")
            success_count += 1
        except:
            pass  # Tránh lỗi khi user chặn bot hoặc không nhận tin nhắn

    bot.send_message(ADMIN_ID, f"✅ Đã gửi thông báo đến {success_count} người dùng.")


# ✅ /start - Chào mừng khách hàng
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = message.chat.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    conn.commit()

    bot.send_message(message.chat.id, "🤖 Chào mừng đến BOT mua link! Bạn có thể:\n"
                                      "💰 /nap_tien - Nạp tiền\n"
                                      "🔍 /so_du - Kiểm tra số dư\n"
                                      "🛒 /mua_link - Mua link")

# ✅ /so_du - Kiểm tra số dư
@bot.message_handler(commands=["so_du"])
def check_balance(message):
    user_id = message.chat.id
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    balance = int(result[0]) if result else 0
    formatted_balance = "{:,}".format(balance).replace(",", ".")

    bot.send_message(message.chat.id, f"💰 Số dư của bạn: {formatted_balance} VND")

# ✅ /nap_tien - Hướng dẫn nạp tiền
@bot.message_handler(commands=["nap_tien"])
def deposit_money(message):
    user_id = message.chat.id
    amount = 100000  # Có thể cho người dùng nhập số tiền nạp
    content = f"NAP{user_id}"  # Nội dung giao dịch

    qr_code_url = f"https://img.vietqr.io/image/ICB-109878256183-compact.png?amount={amount}&addInfo={content}"

    msg_text = (
        "💵 Để nạp tiền, vui lòng chuyển khoản:\n"
        "🏦 *VIETTINBANK*\n"
        "📌 STK: `109878256183`\n"
        "👤 TTK: *CAO DINH TUAN ANH*\n"
        f"💬Nội dung: `{content}`\n\n"
        "✅ 👉 NẠP TỐI THIỂU 10k\n"
        "✅ GỬI BILL ĐỂ ĐƯỢC XÁC NHẬN"
    )

    bot.send_message(message.chat.id, msg_text, parse_mode="MarkdownV2")
    bot.send_photo(message.chat.id, qr_code_url, caption="📌 Mã QR đã tự động điền thông tin để thanh toán nhanh hơn!\n✅ GỬI BILL ĐỂ ĐƯỢC XÁC NHẬN")



# ✅ Lưu ảnh bill khi khách hàng gửi
@bot.message_handler(content_types=["photo"])
def handle_bill_photo(message):
    user_id = message.chat.id
    file_id = message.photo[-1].file_id

    # First ensure the user exists in the database
    cursor.execute("INSERT OR IGNORE INTO users (user_id, balance) VALUES (?, 0)", (user_id,))
    # Then update their last_bill
    cursor.execute("UPDATE users SET last_bill = ? WHERE user_id = ?", (file_id, user_id))
    conn.commit()

    bot.send_message(message.chat.id, "✅BILL ĐÃ ĐƯỢC LƯU! Nhấn /XACNHAN để gửi.")

# ✅ /XACNHAN - Gửi bill cho admin xác nhận
@bot.message_handler(commands=["XACNHAN"])
def confirm_deposit(message):
    user_id = message.chat.id
    cursor.execute("SELECT last_bill FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result or not result[0]:
        bot.send_message(message.chat.id, "❌ Bạn chưa gửi ảnh bill.")
        return

    bill_photo = result[0]

    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Xác nhận + Tiền", callback_data=f"confirm_{user_id}"),
        InlineKeyboardButton("❌ Từ chối", callback_data=f"deny_{user_id}")
    )

    bot.send_photo(ADMIN_ID, bill_photo, caption=f"🔔 *Xác nhận nạp tiền*\n👤 User ID: {user_id}", reply_markup=keyboard)
    bot.send_message(message.chat.id, "✅ Bill đã gửi, chờ xác nhận.")

# ✅ Admin xác nhận nạp tiền
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def handle_admin_confirm(call):
    user_id = call.data.split("_")[1]
    msg = bot.send_message(ADMIN_ID, f"💰 Nhập số tiền muốn cộng cho user {user_id}: ", reply_markup=ForceReply())
    bot.register_next_step_handler(msg, process_add_money, user_id)

def process_add_money(message, user_id):
    try:
        amount = int(message.text)
        cursor.execute("UPDATE users SET balance = balance + ?, last_bill = NULL WHERE user_id = ?", (amount, user_id))
        conn.commit()

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]
        formatted_balance = "{:,}".format(new_balance).replace(",", ".")

        bot.send_message(int(user_id), f"✅ ĐÃ ĐƯỢC XÁC NHẬN, {amount:,} VND ĐÃ ĐƯỢC CỘNG VÀO TK. Số dư hiện tại: {amount:,} VND\n👉 VỀ TRANG CHỦ NHẤN /start")
        bot.send_message(ADMIN_ID, f"✔ Đã cộng {amount:,} VND cho user {user_id}.")
    except ValueError:
        bot.send_message(ADMIN_ID, "❌ Số tiền không hợp lệ. Hãy nhập lại số tiền.")

@bot.callback_query_handler(func=lambda call: call.data.

startswith("deny_"))
def handle_admin_deny(call):
    user_id = call.data.split("_")[1]
    bot.send_message(user_id, "❌ Đã từ chối yêu cầu nạp tiền.")

# ✅ /mua_link - Mua link (Khách nhập link vượt, bot kiểm tra và trừ tiền)
@bot.message_handler(commands=["mua_link"])
def mua_link_step1(message):
    # Yêu cầu khách hàng nhập link vượt
    bot.send_message(message.chat.id, "🔗 Nhập link vượt bạn muốn mua:")
    bot.register_next_step_handler(message, mua_link_step2)

def mua_link_step2(message):
    link_vuot = message.text
    user_id = message.chat.id

    # Kiểm tra link vượt có tồn tại không
    cursor.execute("SELECT original_link, price FROM links WHERE bypass_link = ?", (link_vuot,))
    link_result = cursor.fetchone()

    if not link_result:
        bot.send_message(message.chat.id, "❌ Link không tồn tại hoặc chưa được update. Vui lòng thử lại.")
        return

    # Lấy thông tin link và số dư của khách hàng
    original_link, price = link_result
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()[0]

    # Kiểm tra số dư của khách hàng
    if balance < price:
        bot.send_message(
            message.chat.id,
            f"❌ Bạn không đủ tiền để mua link này.\n\n"
            f"💵 Giá link: {price} VND\n"
            f"💰 Số dư hiện tại: {balance} VND\n\n"
            f"👉 Bạn cần nạp thêm {price - balance} VND để mua link này."
        )
        return

    # Trừ tiền và gửi link cho khách hàng
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
    conn.commit()

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    new_balance = cursor.fetchone()[0]

    formatted_balance = "{:,}".format(int(new_balance)).replace(",", ".")
    bot.send_message(
        message.chat.id,
        f"🎉 Mua link thành công!\n"
        f"🔗 Link của bạn: {original_link}\n"
        f"💰 Số dư còn lại: {formatted_balance} VND\n"
        f"Nhấn /start để trở về trang chủ."
    )

@bot.message_handler(commands=["admin"])
def admin_menu(message):
    # Kiểm tra xem người dùng có phải là admin không
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền truy cập vào menu admin.")
        return

    # Tạo menu lệnh cho admin
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("➕ Thêm link", callback_data="admin_add_link"),
        InlineKeyboardButton("🗑️ Xóa link", callback_data="admin_delete_link"),
        InlineKeyboardButton("👥 Xem danh sách người dùng", callback_data="admin_list_users"),
        InlineKeyboardButton("🔗 Xem danh sách link", callback_data="admin_list_links"),
        InlineKeyboardButton("💰 Cộng/trừ tiền người dùng", callback_data="admin_adjust_balance"),
        InlineKeyboardButton("📢 Gửi thông báo", callback_data="admin_announcement")
    )

    bot.send_message(message.chat.id, "👨‍💻 **Menu Admin**\nChọn một tùy chọn:", reply_markup=keyboard)

# Xử lý lệnh /admin
@bot.callback_query_handler(func=lambda call: call.data == "admin_announcement")
def admin_send_announcement(call):
    if call.message.chat.id != ADMIN_ID:
        bot.send_message(call.message.chat.id, "❌ Bạn không có quyền sử dụng tính năng này.")
        return

    msg = bot.send_message(ADMIN_ID, "📢 Nhập nội dung thông báo:")
    bot.register_next_step_handler(msg, process_announcement)


# Định nghĩa hàm admin_add_link_step1 trước khi gọi
def admin_add_link_step1(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Bạn không có quyền admin.")
        return

    msg = bot.send_message(ADMIN_ID, "🔗 Nhập *link vượt*:")
    bot.register_next_step_handler(msg, admin_add_link_step2)

def admin_add_link_step2(message):
    link_vuot = message.text
    msg = bot.send_message(ADMIN_ID, "🔗 Nhập *link gốc*:")
    bot.register_next_step_handler(msg, admin_add_link_step3, link_vuot)

def admin_add_link_step3(message, link_vuot):
    link_goc = message.text
    msg = bot.send_message(ADMIN_ID, "💰 Nhập *giá bán* (VND):")
    bot.register_next_step_handler(msg, admin_add_link_step4, link_vuot, link_goc)


def admin_add_link_step4(message, link_vuot, link_goc):
            try:
                price = int(message.text)
                save_link(link_vuot, link_goc, price)

                # Dùng escape_markdown để tránh lỗi khi gửi tin nhắn
                msg_text = (
                    f"✅ Đã thêm link\\!\n\n"
                    f"🔗 *Link vượt:* {escape_markdown(link_vuot)}\n"
                    f"🔗 *Link gốc:* {escape_markdown(link_goc)}\n"
                    f"💰 *Giá:* {price} VND"
                )

                bot.send_message(ADMIN_ID, msg_text, parse_mode="MarkdownV2")
            except ValueError:
                bot.send_message(ADMIN_ID, "❌ Giá không hợp lệ. Hãy nhập lại số nguyên.")


# Xử lý callback từ menu admin
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callback(call):
    if call.data == "admin_add_link":
        # Gọi hàm thêm link từng bước
        admin_add_link_step1(call.message)
    elif call.data == "admin_delete_link":
        # Gọi hàm xóa link
        bot.send_message(call.message.chat.id, "🔗 Nhập link vượt bạn muốn xóa:")
        bot.register_next_step_handler(call.message, admin_delete_link)
    elif call.data == "admin_list_users":
        # Hiển thị danh sách người dùng
        list_users(call.message)
    elif call.data == "admin_list_links":
        # Hiển thị danh sách link
        list_links(call.message)
    elif call.data == "admin_adjust_balance":
        # Gọi hàm cộng/trừ tiền người dùng
        bot.send_message(call.message.chat.id, "👤 Nhập ID người dùng:")
        bot.register_next_step_handler(call.message, admin_adjust_balance_step1)

# Xử lý callback từ menu admin
@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callback(call):
    if call.data == "admin_add_link":
        # Gọi hàm thêm link từng bước
        admin_add_link_step1(call.message)
    elif call.data == "admin_delete_link":
        # Gọi hàm xóa link
        bot.send_message(call.message.chat.id, "🔗 Nhập link vượt bạn muốn xóa:")
        bot.register_next_step_handler(call.message, admin_delete_link)
    elif call.data == "admin_list_users":
        # Hiển thị danh sách người dùng
        list_users(call.message)
    elif call.data == "admin_list_links":
        # Hiển thị danh sách link
        list_links(call.message)
    elif call.data == "admin_adjust_balance":
        # Gọi hàm cộng/trừ tiền người dùng
        bot.send_message(call.message.chat.id, "👤 Nhập ID người dùng:")
        bot.register_next_step_handler(call.message, admin_adjust_balance_step1)

# Hàm xóa link
def admin_delete_link(message):
    link_vuot = message.text
    cursor.execute("DELETE FROM links WHERE bypass_link = ?", (link_vuot,))
    if cursor.rowcount > 0:
        conn.commit()
        bot.send_message(message.chat.id, f"✅ Đã xóa link: {link_vuot}")
    else:
        bot.send_message(message.chat.id, "❌ Link không tồn tại.")

# Hàm hiển thị danh sách người dùng
def list_users(message):
        cursor.execute("SELECT user_id, balance FROM users")
        users = cursor.fetchall()

        if not users:
            bot.send_message(message.chat.id, "❌ Không có người dùng nào.")
            return

        user_list = "👥 *Danh sách người dùng:*\n"
        for user_id, balance in users:
            formatted_balance = "{:,}".format(balance).replace(",", ".")
            user_list += f"\\- ID: `{user_id}`, Số dư: `{formatted_balance} VND`\n"

        bot.send_message(message.chat.id, user_list, parse_mode="MarkdownV2")

def list_links(message):
        cursor.execute("SELECT bypass_link, original_link, price FROM links")
        links = cursor.fetchall()

        if not links:
            bot.send_message(message.chat.id, "❌ Không có link nào.")
            return

        link_list = "🔗 *Danh sách link:*\n"
        for bypass_link, original_link, price in links:
                formatted_price = "{:,}".format(price).replace(",", ".")

                link_list += (
                    f"\\- Link vượt: `{escape_markdown(bypass_link)}`\n"
                    f"  Link gốc: `{escape_markdown(original_link)}`\n"
                    f"  Giá: `{formatted_price} VND`\n"
                )

        bot.send_message(message.chat.id, link_list, parse_mode="MarkdownV2")

# Hàm cộng/trừ tiền người dùng
def admin_adjust_balance_step1(message):
    user_id = message.text
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if not result:
        bot.send_message(message.chat.id, "❌ Người dùng không tồn tại.")
        return

    msg = bot.send_message(message.chat.id, "💰 Nhập số tiền (dương để cộng, âm để trừ):")
    bot.register_next_step_handler(msg, admin_adjust_balance_step2, user_id)

def admin_adjust_balance_step2(message, user_id):
    try:
        amount = int(message.text)
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        new_balance = cursor.fetchone()[0]
        formatted_balance = "{:,}".format(new_balance).replace(",", ".")

        bot.send_message(message.chat.id, f"✅ Đã điều chỉnh số dư của người dùng {user_id} thành {formatted_balance} VND.")
    except ValueError:
        bot.send_message(message.chat.id, "❌ Số tiền không hợp lệ. Hãy nhập lại số nguyên.")

# ✅ Tạo server nhỏ để UptimeRobot ping
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

# ✅ Giữ bot chạy liên tục
def keep_alive():
    t = Thread(target=run)
    t.start()

# 💡 Gọi keep_alive() trước khi chạy bot
keep_alive()
bot.polling()
