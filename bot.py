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

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-100123456789"))
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID", "-100987654321"))
STORE_UPI_ID = os.getenv("STORE_UPI_ID", "6398324472@fam")
PORT = int(os.getenv("PORT", 8080))

# Database Setup
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["vj_post_search_db"]
stories_col = db["stories"]
users_col = db["users"]
orders_col = db["orders"]

app = Client("vj_post_search_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 0. HTTP SERVER FOR PORT BINDING ---
async def handle_ping(request):
    return web.Response(text="Bot is Live and Running 24/7!")

routes = [web.get('/', handle_ping), web.get('/health', handle_ping)]

# --- 1. LANGUAGE DICTIONARY ---
TEXTS = {
    "hi": {
        "welcome": "❖ **VJ POST SEARCH BOT** ❖\n\n👋 **नमस्ते {name}!**\nऑडियो स्टोरीज और कंटेंट ब्राउज़ करने के लिए नीचे दिए गए बटनों का उपयोग करें:",
        "btn_catalog": "💎 स्टोरीज कैटलॉग",
        "btn_library": "🛒 मेरी लाइब्रेरी",
        "btn_lang": "🌐 भाषा बदलें (Language)",
        "lang_select": "🌐 **अपनी भाषा चुनें / Select Your Language:**",
        "lang_changed": "✅ **भाषा बदलकर हिंदी कर दी गई है!**",
        "no_stories": "अभी कोई सामग्री उपलब्ध नहीं है।",
        "catalog_title": "📖 **उपलब्ध कैटलॉग:**\nअपनी पसंदीदा स्टोरी पर क्लिक करें:",
        "btn_prev": "⬅️ पिछला",
        "btn_next": "अगला ➡️",
        "not_in_db": "❌ **यह स्टोरी डेटाबेस में उपलब्ध नहीं है।**",
        "unlocked_msg": "\n✅ **आप इसे अनलॉक कर चुके हैं!**",
        "btn_listen": "▶️ अभी सुनें / फाइल देखें",
        "btn_buy": "💳 अभी खरीदें (Buy Now)",
        "btn_back_cat": "🔙 कैटलॉग पर जाएं",
        "pay_instruct": "💳 **पेमेंट निर्देश:**\n\n📖 **स्टोरी:** {title}\n💰 **राशि:** ₹{price}\n🔹 **UPI ID:** `{upi}`\n\n1️⃣ ऊपर दिए गए UPI ID पर भुगतान करें।\n2️⃣ भुगतान के बाद **12-अंकों का UTR/Ref No.** नीचे दिए गए तरीके से भेजें:\n\n`/utr {id} <आपका_12_अंकों_का_UTR>`",
        "btn_cancel": "🔙 रद्द करें",
        "utr_invalid_format": "❌ **गलत फ़ॉर्मेट!**\nसही तरीका: `/utr <story_id> <utr_number>`",
        "utr_invalid_len": "❌ **अमान्य UTR!** UTR नंबर 12 अंकों का होना चाहिए।",
        "utr_exists": "⚠️ यह UTR नंबर पहले ही सबमिट किया जा चुका है!",
        "invalid_story_id": "❌ अमान्य Story ID!",
        "utr_submitted": "✅ **आपका UTR सत्यापन के लिए भेज दिया गया है!**\nस्वीकृति मिलते ही स्टोरी अपने आप अनलॉक हो जाएगी।",
        "my_lib_empty": "आपकी लाइब्रेरी खाली है।",
        "my_lib_title": "🎧 **आपकी अनलॉक्ड स्टोरीज:**"
    },
    "en": {
        "welcome": "❖ **VJ POST SEARCH BOT** ❖\n\n👋 **Hello {name}!**\nUse the buttons below to browse audio stories and content:",
        "btn_catalog": "💎 Stories Catalog",
        "btn_library": "🛒 My Library",
        "btn_lang": "🌐 Change Language",
        "lang_select": "🌐 **Select Your Language / अपनी भाषा चुनें:**",
        "lang_changed": "✅ **Language changed to English successfully!**",
        "no_stories": "No content available right now.",
        "catalog_title": "📖 **Available Catalog:**\nClick on your favorite story:",
        "btn_prev": "⬅️ Previous",
        "btn_next": "Next ➡️",
        "not_in_db": "❌ **This story is not available in the database.**",
        "unlocked_msg": "\n✅ **You have already unlocked this!**",
        "btn_listen": "▶️ Listen Now / View File",
        "btn_buy": "💳 Buy Now",
        "btn_back_cat": "🔙 Back to Catalog",
        "pay_instruct": "💳 **Payment Instructions:**\n\n📖 **Story:** {title}\n💰 **Price:** ₹{price}\n🔹 **UPI ID:** `{upi}`\n\n1️⃣ Pay to the UPI ID provided above.\n2️⃣ After payment, send the **12-digit UTR/Ref No.** in this format:\n\n`/utr {id} <your_12_digit_utr>`",
        "btn_cancel": "🔙 Cancel",
        "utr_invalid_format": "❌ **Wrong Format!**\nCorrect format: `/utr <story_id> <utr_number>`",
        "utr_invalid_len": "❌ **Invalid UTR!** UTR number must be exactly 12 digits.",
        "utr_exists": "⚠️ This UTR number has already been submitted!",
        "invalid_story_id": "❌ Invalid Story ID!",
        "utr_submitted": "✅ **Your UTR has been sent for verification!**\nThe story will be unlocked automatically upon approval.",
        "my_lib_empty": "Your library is empty.",
        "my_lib_title": "🎧 **Your Unlocked Stories:**"
    }
}

# --- HELPER FUNCTIONS ---
def get_or_create_user(user_id):
    user = users_col.find_one({"userId": user_id})
    if not user:
        user = {"userId": user_id, "lang": "hi", "cart": [], "purchasedStories": []}
        users_col.insert_one(user)
    return user

def get_user_lang(user_id):
    user = get_or_create_user(user_id)
    return user.get("lang", "hi")

# --- 1. AUTO-INDUCTION (केवल पहली लाइन इंडेक्सिंग) ---
@app.on_message(filters.chat(SOURCE_CHANNEL_ID) & (filters.document | filters.video | filters.audio | filters.text))
async def auto_induction_handler(client: Client, message: Message):
    caption = message.caption or message.text
    if not caption:
        return

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

# --- 2. START & MAIN MENU HANDLER ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        raw_id = args[1].replace("file_", "").replace("story_", "").strip()
        await send_story_details(message.chat.id, raw_id)
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_catalog"], callback_data="catalog_1")],
            [InlineKeyboardButton(t["btn_library"], callback_data="my_library")],
            [InlineKeyboardButton(t["btn_lang"], callback_data="select_language")]
        ])
        await message.reply_text(
            t["welcome"].format(name=message.from_user.first_name),
            reply_markup=keyboard
        )

# --- 3. LANGUAGE SELECTION HANDLERS ---
@app.on_callback_query(filters.regex(r"^select_language$"))
async def select_language_callback(client: Client, callback: CallbackQuery):
    lang = get_user_lang(callback.from_user.id)
    t = TEXTS[lang]
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇮🇳 हिंदी", callback_data="set_lang_hi"),
            InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
        ],
        [InlineKeyboardButton(t["btn_back_cat"], callback_data="catalog_1")]
    ])
    await callback.message.edit_text(t["lang_select"], reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^set_lang_(hi|en)$"))
async def set_language_callback(client: Client, callback: CallbackQuery):
    new_lang = callback.matches[0].group(1)
    user_id = callback.from_user.id

    users_col.update_one({"userId": user_id}, {"$set": {"lang": new_lang}}, upsert=True)
    t = TEXTS[new_lang]

    await callback.answer(t["lang_changed"], show_alert=True)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t["btn_catalog"], callback_data="catalog_1")],
        [InlineKeyboardButton(t["btn_library"], callback_data="my_library")],
        [InlineKeyboardButton(t["btn_lang"], callback_data="select_language")]
    ])
    await callback.message.edit_text(
        t["welcome"].format(name=callback.from_user.first_name),
        reply_markup=keyboard
    )

# --- 4. CATALOG & PAGINATION ---
@app.on_callback_query(filters.regex(r"^catalog_(\d+)"))
async def show_catalog(client: Client, callback: CallbackQuery):
    lang = get_user_lang(callback.from_user.id)
    t = TEXTS[lang]

    page = int(callback.matches[0].group(1))
    limit = 5
    skip = (page - 1) * limit

    total_stories = stories_col.count_documents({})
    stories = list(stories_col.find().skip(skip).limit(limit))

    if not stories:
        await callback.answer(t["no_stories"], show_alert=True)
        return

    buttons = []
    for s in stories:
        buttons.append([InlineKeyboardButton(f"🎧 {s.get('title', 'Untitled')} - ₹{s.get('price', 49)}", callback_data=f"story_{s['id']}")])

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(t["btn_prev"], callback_data=f"catalog_{page - 1}"))
    if (skip + limit) < total_stories:
        nav_buttons.append(InlineKeyboardButton(t["btn_next"], callback_data=f"catalog_{page + 1}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(t["btn_lang"], callback_data="select_language")])

    await callback.message.edit_text(
        t["catalog_title"],
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- 5. STORY DETAILS ---
async def send_story_details(chat_id, story_id, edit_message=None):
    lang = get_user_lang(chat_id)
    t = TEXTS[lang]

    story = stories_col.find_one({"id": str(story_id)})
    if not story:
        text = t["not_in_db"]
        if edit_message: await edit_message.edit_text(text)
        else: await app.send_message(chat_id, text)
        return

    user = get_or_create_user(chat_id)
    is_purchased = str(story_id) in user.get("purchasedStories", [])

    caption = (
        f"🎧 **{story.get('title', 'Untitled')}**\n\n"
        f"💰 **Price / मूल्य:** ₹{story.get('price', 49)}\n"
        f"🆔 **ID:** `{story['id']}`\n"
    )

    if is_purchased:
        caption += t["unlocked_msg"]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_listen"], callback_data=f"getfile_{story['id']}")],
            [InlineKeyboardButton(t["btn_back_cat"], callback_data="catalog_1")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_buy"], callback_data=f"buy_{story['id']}")],
            [InlineKeyboardButton(t["btn_back_cat"], callback_data="catalog_1")]
        ])

    if edit_message:
        await edit_message.edit_text(caption, reply_markup=keyboard)
    else:
        await app.send_message(chat_id, caption, reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^story_(.+)"))
async def story_callback(client: Client, callback: CallbackQuery):
    story_id = callback.matches[0].group(1)
    await send_story_details(callback.message.chat.id, story_id, edit_message=callback.message)

# --- 6. BUY & UPI PAYMENT ---
@app.on_callback_query(filters.regex(r"^buy_(.+)"))
async def buy_story_callback(client: Client, callback: CallbackQuery):
    lang = get_user_lang(callback.from_user.id)
    t = TEXTS[lang]

    story_id = callback.matches[0].group(1)
    story = stories_col.find_one({"id": str(story_id)})

    if not story:
        await callback.answer(t["not_in_db"], show_alert=True)
        return

    msg_text = t["pay_instruct"].format(
        title=story.get('title'),
        price=story.get('price', 49),
        upi=STORE_UPI_ID,
        id=story['id']
    )

    await callback.message.edit_text(
        msg_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t["btn_cancel"], callback_data=f"story_{story_id}")]
        ])
    )

# --- 7. UTR SUBMISSION & LOG CHANNEL ---
@app.on_message(filters.command("utr") & filters.private)
async def handle_utr_submit(client: Client, message: Message):
    user = message.from_user
    lang = get_user_lang(user.id)
    t = TEXTS[lang]

    args = message.text.split()
    if len(args) < 3:
        await message.reply_text(t["utr_invalid_format"])
        return

    story_id = args[1].strip()
    utr = args[2].strip()

    if not re.match(r"^\d{12}$", utr):
        await message.reply_text(t["utr_invalid_len"])
        return

    if orders_col.find_one({"utr": utr}):
        await message.reply_text(t["utr_exists"])
        return

    story = stories_col.find_one({"id": str(story_id)})
    if not story:
        await message.reply_text(t["invalid_story_id"])
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

    await message.reply_text(t["utr_submitted"])

    log_msg = (
        f"💳 **New Payment Verification Alert!**\n\n"
        f"👤 **User:** {order_doc['username']} (`{user.id}`)\n"
        f"📖 **Story:** {story.get('title')}\n"
        f"💰 **Amount:** ₹{story.get('price', 49)}\n"
        f"🔢 **UTR:** `{utr}`"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"appr_{utr}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"rej_{utr}")
        ]
    ])
    await client.send_message(LOG_CHANNEL_ID, log_msg, reply_markup=keyboard)

# --- 8. ADMIN APPROVAL HANDLER ---
@app.on_callback_query(filters.regex(r"^(appr|rej)_(.+)"))
async def handle_order_approval(client: Client, callback: CallbackQuery):
    action = callback.matches[0].group(1)
    utr = callback.matches[0].group(2)

    order = orders_col.find_one({"utr": utr})
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    if action == "appr":
        orders_col.update_one({"utr": utr}, {"$set": {"status": "Approved"}})
        users_col.update_one({"userId": order["userId"]}, {"$addToSet": {"purchasedStories": order["storyId"]}}, upsert=True)

        await callback.message.edit_text(f"{callback.message.text}\n\n✅ **STATUS: APPROVED**")
        await callback.answer("Approved successfully!")

        try:
            u_lang = get_user_lang(order["userId"])
            msg = "🎉 **पेमेंट सत्यापित हो गया!**\n\nआपकी स्टोरी अनलॉक हो चुकी है।" if u_lang == "hi" else "🎉 **Payment Verified!**\n\nYour story has been unlocked."
            await app.send_message(order["userId"], msg)
        except Exception:
            pass
    else:
        orders_col.update_one({"utr": utr}, {"$set": {"status": "Rejected"}})
        await callback.message.edit_text(f"{callback.message.text}\n\n❌ **STATUS: REJECTED**")
        await callback.answer("Rejected!")

# --- 9. MY LIBRARY ---
@app.on_callback_query(filters.regex(r"^my_library$"))
async def my_library(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    lang = get_user_lang(user_id)
    t = TEXTS[lang]

    user = get_or_create_user(user_id)
    purchased_ids = user.get("purchasedStories", [])

    if not purchased_ids:
        await callback.answer(t["my_lib_empty"], show_alert=True)
        return

    stories = list(stories_col.find({"id": {"$in": purchased_ids}}))
    buttons = []
    for s in stories:
        buttons.append([InlineKeyboardButton(f"▶️ {s.get('title')}", callback_data=f"story_{s['id']}")])

    buttons.append([InlineKeyboardButton(t["btn_back_cat"], callback_data="catalog_1")])

    await callback.message.edit_text(
        t["my_lib_title"],
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- START BOT AND HTTP SERVER ---
if __name__ == "__main__":
    web_app = web.Application()
    web_app.add_routes(routes)
    
    runner = web.AppRunner(web_app)
    app.loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    app.loop.run_until_complete(site.start())
    print(f"HTTP Server binds successfully on port {PORT}")

    app.run()
