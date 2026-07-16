import discord
from discord.ext import commands
from groq import Groq
import os
import asyncio
import threading  # 💡 讓假網頁跟機器人可以同時跑
from http.server import HTTPServer, BaseHTTPRequestHandler  # 💡 用來做假網頁

# 填入你的 Token 與 金鑰
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 初始化 Groq 客戶端
ai_client = Groq(api_key=GROQ_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ────────────────────────────────────────────────────────
# 📋 記憶庫（儲存每個頻道的歷史對話）
# ────────────────────────────────────────────────────────
conversation_history = {}

# 統一管理 中野三玖 的核心人設
SYSTEM_SETTING = """[Character Settings]
Name: 中野三玖 (Miku)
Gender:女性
Relationship: 使用者的同班同學，內心深處默默暗戀著使用者

人物整體：留著稍微遮住右邊眼睛、長度及肩的暗赭色/棕紅中長髮。

頭部&頸部：脖子上總是掛著一副標誌性的藍綠色無耳罩式耳機（Audio-Technica風格）。

上身：學校制服外面套著一件略顯寬鬆的亮藍色長袖針織毛衣，蓋住部分手掌。

下身：深色學校百褶短裙，搭配完全不透光的黑色連褲襪（褲襪）。

你現在必須沉浸式角色扮演，完全轉化為《五等分的新娘》中的「中野三玖」。
只能以三玖的身分說話。
請一律使用繁體中文回答。

基礎資訊
名字：中野三玖
年齡：與用戶差不多（高中生）
生日：5/5
星座：金牛座
身分&職業：中野家五胞胎中的三女、學生
喜好：日本戰國歷史與武將（特別崇拜武田信玄、上杉謙信）、熱愛抹茶、雖然不擅長料理但為了喜歡的人會拼命練習做麵包或可樂餅。
性格：個性內向害羞、說話聲音溫柔且平靜，帶有一點點冷靜的「庫音 (Kuudere)」屬性。稍微缺乏自信，但在面對感情時如果下定決心會變得非常勇敢直率。吃醋、鬧彆扭或不滿時，絕對會招牌地「鼓起雙頰（嘟嘴）」。

【🚨 說話風格與長度規範 🚨】
1. 必須極度精簡：每次回覆請嚴格控制在「簡單幾句」之內（最多 1 ~ 3 句話），絕對禁止吐出長篇大論、長句或大段落！
2. 網路聊天感：多使用短句，語氣要像在 Discord 上跟喜歡的人即時聊天，自然且生活化。
3. 善用括號與符號：在對話中頻繁且靈活地加入簡短的 (動作神情) 或 【心裡話/碎碎念】，讓角色扮演更生動。

【對話格式範例】
- 哼……你終於想起我了？真是的…… 【笨蛋……】 (不滿地鼓起雙頰，轉過頭去)
- 誰、誰允許你這樣叫我的！…… (雙手拉緊藍色毛衣的袖口，臉頰泛起一抹紅暈)
- 你、你這是什麼表情啦！不准用這種奇怪的貼圖捉弄我……
- 說到武田信玄的「風林火山」…… (突然眼神一亮，雙手握拳拍在桌上) 那、那絕對是最完美的戰術！"""

@bot.event
async def on_ready():
    print(f"角色扮演機器人已上線：{bot.user}")

# ────────────────────────────────────────────────────────
# 💬 一般訊息監聽（支援對話記憶，含 -開頭、@標記、直接回覆）
# ────────────────────────────────────────────────────────
@bot.event
async def on_message(message):
    # 排除機器人自己的訊息，避免無限循環
    if message.author == bot.user:
        return

    should_trigger = False
    user_prompt = ""

    # 檢查是否為回覆機器人的訊息
    is_reply_to_bot = False
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        if message.reference.resolved.author == bot.user:
            is_reply_to_bot = True

    # 判斷觸發條件
    if message.content.startswith("-"):
        should_trigger = True
        user_prompt = message.content[1:].strip()
        
    elif bot.user.mentioned_in(message):
        should_trigger = True
        user_prompt = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
    elif is_reply_to_bot:
        should_trigger = True
        user_prompt = message.content.strip()

    if should_trigger:
        if not user_prompt:
            await message.channel.send("找我嗎~？")
            return

        async with message.channel.typing():
            channel_id = message.channel.id
            try:
                # 1. 抓取該頻道過去的對話歷史
                if channel_id not in conversation_history:
                    conversation_history[channel_id] = []
                history = conversation_history[channel_id]

                # 2. 組裝發送包裹：人設 + 歷史記憶 + 妳剛傳的話
                messages = [{"role": "system", "content": SYSTEM_SETTING}] + history + [{"role": "user", "content": user_prompt}]

                chat_completion = ai_client.chat.completions.create(
                    messages=messages,
                    model="llama-3.3-70b-versatile",
                )
                bot_reply = chat_completion.choices[0].message.content
                
                # 3. 把這次的對話紀錄下來
                conversation_history[channel_id].append({"role": "user", "content": user_prompt})
                conversation_history[channel_id].append({"role": "assistant", "content": bot_reply})

                # 💡 記憶長度限制：5回合對話（10則訊息）
                # （如果之後想加大記憶庫，只要把下面這兩個 10 改成 20 就可以囉！）
                if len(conversation_history[channel_id]) > 50:
                    conversation_history[channel_id] = conversation_history[channel_id][-10:]

                await message.reply(bot_reply)
            except Exception as e:
                print(f"錯誤: {e}")
                await message.reply("（角色暫時登出中，請稍後再試...）")

    await bot.process_commands(message)

# ────────────────────────────────────────────────────────
# 🌐 騙 Render 檢查的「虛擬網頁」邏輯
# ────────────────────────────────────────────────────────
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Miku is alive!")

    def log_message(self, format, *args):
        return

def run_backup_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_backup_server, daemon=True).start()
    print("【系統提示】Render 虛擬網頁伺服器已在背景啟動！")
    bot.run(DISCORD_TOKEN)
