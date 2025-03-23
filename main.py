import telebot
import json
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from flask import Flask
from threading import Thread
import telebot.util
from telebot.formatting import escape_markdown  # Import hàm escape_markdown

# ✅ Cấu hình bot
TOKEN = "7815604030:AAELtDIikq3XylIwzwITArq-kjrFP6EFwsM"
ADMIN_ID = 6283529520  # Thay bằng Telegram ID của admin

bot = telebot.TeleBot(TOKEN)

# Định dạng số tiền
def format_currency(amount):
    return "{:,}".format(amount).replace(",", ".")


# ✅ Load & Lưu dữ liệu JSON
def load_data():
    try:
        with open("data.json", "r") as file:
            return json.load(file)
    except:
        return {"users": {}, "links": {}}

def save_data(data):
    with open("data.json", "w") as file:
        json.dump(data, file, indent=4)


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
    data = load_data()
    users = data["users"]

    if not users:
        bot.send_message(ADMIN_ID, "❌ Không có người dùng nào để gửi thông báo.")
        return

    success_count = 0
    for user_id in users.keys():
        try:
            bot.send_message(user_id, f"📢 *Thông báo từ Admin:*\n{content}", parse_mode="Markdown")
            success_count += 1
        except:
            pass  # Tránh lỗi khi user chặn bot hoặc không nhận tin nhắn

    bot.send_message(ADMIN_ID, f"✅ Đã gửi thông báo đến {success_count} người dùng.")


# ✅ /start - Chào mừng khách hàng
@bot.message_handler(commands=["start"])
def send_welcome(message):
    user_id = str(message.chat.id)
    data = load_data()

    if user_id not in data["users"]:
        data["users"][user_id] = {"balance": 0}
        save_data(data)

    bot.send_message(message.chat.id, "🤖 Chào mừng! Bạn có thể:\n"
                                      "💰 /nap_tien - Nạp tiền\n"
                                      "🔍 /so_du - Kiểm tra số dư\n"
                                      "🛒 /mua_link [link vượt] - Mua link")

# ✅ /so_du - Kiểm tra số dư
@bot.message_handler(commands=["so_du"])
def check_balance(message):
    user_id = str(message.chat.id)
    data = load_data()

    balance = data["users"].get(user_id, {}).get("balance", 0)
    formatted_balance = format_currency(balance)# Định dạng tiền

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
    user_id = str(message.chat.id)
    file_id = message.photo[-1].file_id  

    data = load_data()
    data["users"][user_id]["last_bill"] = file_id
    save_data(data)

    bot.send_message(message.chat.id, "✅BILL ĐÃ ĐƯỢC LƯU! Nhấn /XACNHAN để gửi.")

# ✅ /XACNHAN - Gửi bill cho admin xác nhận
@bot.message_handler(commands=["XACNHAN"])
def confirm_deposit(message):
    user_id = str(message.chat.id)
    data = load_data()

    if "last_bill" not in data["users"].get(user_id, {}):
        bot.send_message(message.chat.id, "❌ Bạn chưa gửi ảnh bill.")
        return

    bill_photo = data["users"][user_id]["last_bill"]

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
        data = load_data()
        data["users"][user_id]["balance"] += amount
        del data["users"][user_id]["last_bill"]
        save_data(data)

        bot.send_message(user_id, f"✅ ĐÃ ĐƯỢC XÁC NHẬN, {amount} VND ĐÃ ĐƯỢC CỘNG VÀO TK.VỀ TRANG CHỦ NHẤN /start")
        bot.send_message(ADMIN_ID, f"✔ Đã cộng {amount} VND cho user {user_id}.")
    except:
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
    user_id = str(message.chat.id)
    data = load_data()

    # Kiểm tra link vượt có tồn tại không
    if link_vuot not in data["links"]:
        bot.send_message(message.chat.id, "❌ Link không tồn tại hoặc chưa được update. Vui lòng thử lại.")
        return

    # Lấy thông tin link và số dư của khách hàng
    link_info = data["links"][link_vuot]
    price = link_info["price"]
    balance = data["users"][user_id]["balance"]

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
    data["users"][user_id]["balance"] -= price
    save_data(data)

    bot.send_message(
        message.chat.id,
        f"🎉 Mua link thành công!\n"
        f"🔗 Link của bạn: {link_info['url']}\n"
        f"💰 Số dư còn lại: {data['users'][user_id]['balance']} VND\n"
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
                data = load_data()
                data["links"][link_vuot] = {"url": link_goc, "price": price}
                save_data(data)

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
    data = load_data()

    if link_vuot in data["links"]:
        del data["links"][link_vuot]
        save_data(data)
        bot.send_message(message.chat.id, f"✅ Đã xóa link: {link_vuot}")
    else:
        bot.send_message(message.chat.id, "❌ Link không tồn tại.")

# Hàm hiển thị danh sách người dùng
def list_users(message):
        data = load_data()
        users = data["users"]

        if not users:
            bot.send_message(message.chat.id, "❌ Không có người dùng nào.")
            return

        user_list = "👥 *Danh sách người dùng:*\n"
        for user_id, user_data in users.items():
            user_list += f"\\- ID: `{user_id}`, Số dư: `{user_data['balance']} VND`\n"

        bot.send_message(message.chat.id, user_list, parse_mode="MarkdownV2")

def list_links(message):
        data = load_data()
        links = data["links"]

        if not links:
            bot.send_message(message.chat.id, "❌ Không có link nào.")
            return

        link_list = "🔗 *Danh sách link:*\n"
        for link_vuot, link_data in links.items():
                formatted_price = "{:,}".format(link_data['price']).replace(",", ".")

                link_list += (
                    f"\\- Link vượt: `{escape_markdown(link_vuot)}`\n"
                    f"  Link gốc: `{escape_markdown(link_data['url'])}`\n"
                    f"  Giá: `{formatted_price} VND`\n"
            )

        bot.send_message(message.chat.id, link_list, parse_mode="MarkdownV2")

# Hàm cộng/trừ tiền người dùng
def admin_adjust_balance_step1(message):
    user_id = message.text
    data = load_data()

    if user_id not in data["users"]:
        bot.send_message(message.chat.id, "❌ Người dùng không tồn tại.")
        return

    msg = bot.send_message(message.chat.id, "💰 Nhập số tiền (dương để cộng, âm để trừ):")
    bot.register_next_step_handler(msg, admin_adjust_balance_step2, user_id)

def admin_adjust_balance_step2(message, user_id):
    try:
        amount = int(message.text)
        data = load_data()
        data["users"][user_id]["balance"] += amount
        save_data(data)

        bot.send_message(message.chat.id, f"✅ Đã điều chỉnh số dư của người dùng {user_id} thành {data['users'][user_id]['balance']} VND.")
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
