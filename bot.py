import os
import re
from datetime import datetime
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pymongo import MongoClient

# --- CONFIGURATION (Environment Variables) ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "1234567"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
MONGO_URI = os.getenv("MONGO_URI", "YOUR_MONGO_URI")

# Channel IDs
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-100123456789"))
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-100987654321"))
STORE_UPI_ID = os.getenv("STORE_UPI_ID", "6398324472@fam")
PORT = int(os.getenv("PORT", 8080)) # Web Server Port for Hosting Platform

# Database Setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["vj_post_search_db"]
stories_col = db["stories"]
users_col = db["users"]
orders_col = db["orders"]

app = Client("vj_post_search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 0. DUMMY HTTP SERVER FOR PORT BINDING & HEALTH CHECKS ---
async def handle_ping(request):
    return web.Response(text="Bot is Live and Running 24/7!")

routes = [web.get('/', handle_ping), web.get('/health', handle_ping)]

# --- HELPER FUNCTIONS ---
def get_or_create_user(user_id):
    user = users_col.find_one({"userId": user_id})
    if not user:
        user = {"userId": user_id, "cart": [], "purchasedStories": []}
        users_col.insert_one(user)
    return user

# --- 1. AUTO-INDUCTION (चैनल से ऑटोमैटिक टाइटल इंडेक्सिंग) ---
@app.on_message(filters.chat(SOURCE_CHANNEL_ID) & (filters.document | filters.video | filters.audio | filters.text))
async def auto_induction_handler(client: Client, message: Message):
    caption = message.caption or message.text
    if not caption:
        return

    # नियम के अनुसार केवल कैप्शन की पहली लाइन ही टाइटल बनेगी
    first_line_title = caption.split("\n")[0].strip()
    story_id = str(message.id)

    stories_col.update_one(
        {"id": story_id},
        {"$set": {
            "id": story_id,
            "title": first_line_title,
            "full_caption": caption,
            "message_id": message.id,
            "price": 49,
            "created_at": datetime.now()
        }},
        upsert=True
    )

# --- 2. START & SEARCH HANDLER ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    get_or_create_user(user_id)

    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        raw_id = args[1].replace("file_", "").replace("story_", "").strip()
        await send_story_details(message.chat.id, raw_id)
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 स्टोरीज कैटलॉग", callback_data="catalog_1")],
            [InlineKeyboardButton("🛒 मेरी लाइब्रेरी", callback_data="my_library")]
        ])
        await message.reply_text(
            f"❖ **VJ POST SEARCH BOT** ❖\n\n"
            f"👋 **नमस्ते {message.from_user.first_name}!**\n"
            f"ऑडियो स्टोरीज और कंटेंट ब्राउज़ करने के लिए नीचे दिए गए बटनों का उपयोग करें:",
            reply_markup=keyboard
        )

# --- 3. CATALOG & PAGINATION ---
@app.on_callback_query(filters.regex(r"^catalog_(\d+)"))
async def show_catalog(client: Client, callback: CallbackQuery):
    page = int(callback.matches[0].group(1))
    limit = 5
    skip = (page - 1) * limit

    total_stories = stories_col.count_documents({})
    stories = list(stories_col.find().skip(skip).limit(limit))

    if not stories:
        await callback.answer("अभी कोई सामग्री उपलब्ध नहीं है।", show_alert=True)
        return

    buttons = []
    for s in stories:
        buttons.append([InlineKeyboardButton(f"🎧 {s.get('title', 'Untitled')} - ₹{s.get('price', 49)}", callback_data=f"story_{s['id']}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ पिछला", callback_data=f"catalog_{page - 1}"))
    if (skip + limit) < total_stories:
        nav_buttons.append(InlineKeyboardButton("अगला ➡️", callback_data=f"catalog_{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    await callback.message.edit_text(
        "📖 **उपलब्ध कैटलॉग:**\nअपनी पसंदीदा स्टोरी पर क्लिक करें:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- 4. STORY DETAILS & PURCHASE CHECK ---
async def send_story_details(chat_id, story_id, edit_message=None):
    story = stories_col.find_one({"id": str(story_id)})
    if not story:
        text = "❌ **यह स्टोरी डेटाबेस में उपलब्ध नहीं है।**"
        if edit_message: await edit_message.edit_text(text)
        else: await app.send_message(chat_id, text)
        return

    user = get_or_create_user(chat_id)
    is_purchased = str(story_id) in user.get("purchasedStories", [])

    caption = (
        f"🎧 **{story.get('title', 'Untitled')}**\n\n"
        f"💰 **मूल्य:** ₹{story.get('price', 49)}\n"
        f"🆔 **ID:** `{story['id']}`\n"
    )

    if is_purchased:
        caption += "\n✅ **आप इसे अनलॉक कर चुके हैं!**"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ अभी सुनें / फाइल देखें", callback_data=f"getfile_{story['id']}")],
            [InlineKeyboardButton("🔙 कैटलॉग पर जाएं", callback_data="catalog_1")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 अभी खरीदें (Buy Now)", callback_data=f"buy_{story['id']}")],
            [InlineKeyboardButton("🔙 कैटलॉग पर जाएं", callback_data="catalog_1")]
        ])

    if edit_message:
        await edit_message.edit_text(caption, reply_markup=keyboard)
    else:
        await app.send_message(chat_id, caption, reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^story_(.+)"))
async def story_callback(client: Client, callback: CallbackQuery):
    story_id = callback.matches[0].group(1)
    await send_story_details(callback.message.chat.id, story_id, edit_message=callback.message)

# --- 5. BUY & UPI PAYMENT INSTRUCTIONS ---
@app.on_callback_query(filters.regex(r"^buy_(.+)"))
async def buy_story_callback(client: Client, callback: CallbackQuery):
    story_id = callback.matches[0].group(1)
    story = stories_col.find_one({"id": str(story_id)})

    if not story:
        await callback.answer("स्टोरी नहीं मिली!", show_alert=True)
        return

    msg_text = (
        f"💳 **पेमेंट निर्देश:**\n\n"
        f"📖 **स्टोरी:** {story.get('title')}\n"
        f"💰 **राशि:** ₹{story.get('price', 49)}\n"
        f"🔹 **UPI ID:** `{STORE_UPI_ID}`\n\n"
        f"1️⃣ ऊपर दिए गए UPI ID पर भुगतान करें।\n"
        f"2️⃣ भुगतान के बाद **12-अंकों का UTR/Ref No.** नीचे दिए गए तरीके से भेजें:\n\n"
        f"`/utr {story['id']} <आपका_12_अंकों_का_UTR>`"
    )

    await callback.message.edit_text(
        msg_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 रद्द करें", callback_data=f"story_{story_id}")]
        ])
    )

# --- 6. UTR SUBMISSION & LOG CHANNEL ---
@app.on_message(filters.command("utr") & filters.private)
async def handle_utr_submit(client: Client, message: Message):
    args = message.text.split()
    if len(args) < 3:
        await message.reply_text("❌ **गलत फ़ॉर्मेट!**\nसही तरीका: `/utr <story_id> <utr_number>`")
        return

    story_id = args[1].strip()
    utr = args[2].strip()
    user = message.from_user

    if not re.match(r"^\d{12}$", utr):
        await message.reply_text("❌ **अमान्य UTR!** UTR नंबर 12 अंकों का होना चाहिए।")
        return

    if orders_col.find_one({"utr": utr}):
        await message.reply_text("⚠️ यह UTR नंबर पहले ही सबमिट किया जा चुका है!")
        return

    story = stories_col.find_one({"id": str(story_id)})
    if not story:
        await message.reply_text("❌ अमान्य Story ID!")
        return

    order_doc = {
        "userId": user.id,
        "username": f"@{user.username}" if user.username else user.first_name,
        "utr": utr,
        "storyId": str(story_id),
        "storyTitle": story.get("title", "Untitled"),
        "price": story.get("price", 49),
        "status": "Pending",
        "createdAt": datetime.now()
    }
    orders_col.insert_one(order_doc)

    await message.reply_text("✅ **आपका UTR सत्यापन के लिए भेज दिया गया है!**\nस्वीकृति मिलते ही स्टोरी अपने आप अनलॉक हो जाएगी।")

    log_msg = (
        f"💳 **नया पेमेंट वेरिफिकेशन अलर्ट!**\n\n"
        f"👤 **यूजर:** {order_doc['username']} (`{user.id}`)\n"
        f"📖 **स्टोरी:** {story.get('title')}\n"
        f"💰 **राशि:** ₹{story.get('price', 49)}\n"
        f"🔢 **UTR:** `{utr}`"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"appr_{utr}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{utr}")
        ]
    ])
    await client.send_message(LOG_CHANNEL_ID, log_msg, reply_markup=keyboard)

# --- 7. ADMIN APPROVAL HANDLER ---
@app.on_callback_query(filters.regex(r"^(appr|rej)_(.+)"))
async def handle_order_approval(client: Client, callback: CallbackQuery):
    action = callback.matches[0].group(1)
    utr = callback.matches[0].group(2)

    order = orders_col.find_one({"utr": utr})
    if not order:
        await callback.answer("ऑर्डर नहीं मिला!", show_alert=True)
        return

    if action == "appr":
        orders_col.update_one({"utr": utr}, {"$set": {"status": "Approved"}})
        users_col.update_one({"userId": order["userId"]}, {"$addToSet": {"purchasedStories": order["storyId"]}}, upsert=True)

        await callback.message.edit_text(f"{callback.message.text}\n\n✅ **STATUS: APPROVED**")
        await callback.answer("सफलतापूर्वक अप्रूव किया गया!")

        try:
            await app.send_message(
                order["userId"],
                f"🎉 **पेमेंट सत्यापित हो गया!**\n\nआपकी स्टोरी **{order['storyTitle']}** अनलॉक हो चुकी है।"
            )
        except Exception:
            pass
    else:
        orders_col.update_one({"utr": utr}, {"$set": {"status": "Rejected"}})
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ **STATUS: REJECTED**")
        await callback.answer("रिजेक्ट किया गया!")

# --- 8. MY LIBRARY ---
@app.on_callback_query(filters.regex(r"^my_library$"))
async def my_library(client: Client, callback: CallbackQuery):
    user = get_or_create_user(callback.from_user.id)
    purchased_ids = user.get("purchasedStories", [])

    if not purchased_ids:
        await callback.answer("आपकी लाइब्रेरी खाली है।", show_alert=True)
        return

    stories = list(stories_col.find({"id": {"$in": purchased_ids}}))
    buttons = []
    for s in stories:
        buttons.append([InlineKeyboardButton(f"▶️ {s.get('title')}", callback_data=f"story_{s['id']}")])

    buttons.append([InlineKeyboardButton("🔙 कैटलॉग", callback_data="catalog_1")])

    await callback.message.edit_text(
        "🎧 **आपकी अनलॉक्ड स्टोरीज:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- START BOT AND HTTP SERVER TOGETHER ---
if __name__ == "__main__":
    web_app = web.Application()
    web_app.add_routes(routes)
    
    # HTTP Server runner
    runner = web.AppRunner(web_app)
    app.loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    app.loop.run_until_complete(site.start())
    print(f"HTTP Server binds successfully on port {PORT}")

    # Run Pyrogram Client
    app.run()
