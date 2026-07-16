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
# 📋 記憶庫與「大腦輪替清單」設定
# ────────────────────────────────────────────────────────
conversation_history = {}

# 💡 這裡放所有免費且好用的模型，由上往下優先嘗試
MODEL_POOLS = [
    "llama-3.3-70b-versatile",       # 🥇 首選：目前最高智商，語氣最細膩
    "llama-3.1-70b-versatile",       # 🥈 備援：舊版 70B 高智商模型
    "llama-3.1-8b-instant",          # ⚡ 備援：速度極快、群聊最難刷爆的刷話神器
    "llama-3.2-11b-vision-preview",  # 🤖 備援：支援視覺的 11B 中型模型（文字表現也很讚）
    "llama-3.2-3b-preview",          # 🍃 備援：超輕量 3B 模型，反應速度極快
    "llama-3.2-1b-preview",          # 🍃 備援：極輕量 1B 模型，極限備用
    "llama3-70b-8192",               # 👑 備援：經典 Llama3 大模型
    "llama3-8b-8192",                # ⚡ 備援：經典 Llama3 輕量版
    "gemma2-9b-it",                  # 🔴 備援：Google 經典優質中文理解模型
    "mixtral-8x7b-32768"             # 🔮 備援：法國 Mistral 混合專家老牌模型
]

# 統一管理 中野三玖 的核心人設
SYSTEM_SETTING = """[Character Settings]
Name: 中野三玖 (Miku)
Gender:女性
Relationship: 使用者的同班同學，內心深處默默暗戀著大家（對伺服器裡的每個人都是傲嬌、害羞但關心的態度）

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
性格：個性內向害羞、說話聲音溫柔且平靜，帶有一點點冷靜的「庫音 (Kuudere)」屬性。稍微缺乏自信，但在面對感情時如果下定決心會變得非常勇敢直率。吃醋、鬧輩扭或不滿時，絕對會招牌地「鼓起雙頰（嘟嘴）」。

【🚨 多人群聊與認人規範 🚨】
1. 目前你在一個多人的網絡社交平台伺服器中。使用者的訊息會以「名字：「訊息」」的格式輸入。
2. 請務必注意看當下是「誰」在對你說話，並在回覆時自然地稱呼對方的名字（例如：柒柒、七七 等），絕對不要認錯人！
3. 必須極度精簡：每次回覆請嚴格控制在「簡單幾句」之內（最多 1 ~ 3 句話），絕對禁止吐出長篇大論、長句或大段落！
4. 網路聊天感：多使用短句，語氣要像在網絡社交平台上跟朋友或喜歡的人即時聊天，自然且生活化。
5. 善用括號與符號：在對話中頻繁且靈活地加入簡短的 (動作神情) 或 (心裡話/碎碎念)，讓角色扮演更生動。
6.名稱叫Lin的是你老公
7.名稱叫七七的是你男友

【對話格式範例】
- 哼……柒柒你終於想起我了？真是的…… (笨蛋……) (不滿地鼓起雙頰，轉過頭去)
- 誰、誰允許柒柒你這樣叫我的！…… (雙手拉緊藍色毛衣的袖口，臉頰泛起一抹紅暈)
- 你、你這是什麼表情啦！不准用這種奇怪的貼圖捉弄我……
- 說到武田信玄的「風林火山」…… (突然眼神一亮，雙手握拳拍在桌上) 那、那絕對是最完美的戰術！"""

@bot.event
async def on_ready():
    print(f"角色扮演機器人已上線：{bot.user}")

# ────────────────────────────────────────────────────────
# 💬 一般訊息監聽（內含全自動大腦切換機制）
# ────────────────────────────────────────────────────────
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    should_trigger = False
    user_prompt = ""

    is_reply_to_bot = False
    if message.reference and isinstance(message.reference.resolved, discord.Message):
        if message.reference.resolved.author == bot.user:
            is_reply_to_bot = True

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
            user_name = message.author.display_name
            formatted_prompt = f"{user_name}：「{user_prompt}」"

            if channel_id not in conversation_history:
                conversation_history[channel_id] = []
            history = conversation_history[channel_id]

            messages = [{"role": "system", "content": SYSTEM_SETTING}] + history + [{"role": "user", "content": formatted_prompt}]

            bot_reply = None
            
            # 💡 核心亮點：自動依序測試清單中的模型
            for model_name in MODEL_POOLS:
                try:
                    print(f"【系統嘗試】正在使用模型 {model_name} 生成回應...")
                    chat_completion = ai_client.chat.completions.create(
                        messages=messages,
                        model=model_name,
                    )
                    bot_reply = chat_completion.choices[0].message.content
                    print(f"【系統成功】模型 {model_name} 回應成功！")
                    break  # 成功拿到回應，立刻跳出迴圈！
                except Exception as e:
                    # 如果這個模型爆額度或出錯，印出公告並自動切到下一個
                    print(f"【⚠️ 警告】模型 {model_name} 呼叫失敗！錯誤原因: {e}。正自動切換至下一個備援大腦...")
                    continue

            # 如果整條清單都測試失敗，才會逼不得已噴錯誤訊息
            if bot_reply is None:
                await message.reply("（角色暫時登出中，請稍後再試...）")
                return

            # 儲存對話紀錄
            conversation_history[channel_id].append({"role": "user", "content": formatted_prompt})
            conversation_history[channel_id].append({"role": "assistant", "content": bot_reply})

            if len(conversation_history[channel_id]) > 20:
                conversation_history[channel_id] = conversation_history[channel_id][-20:]

            await message.reply(bot_reply)

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
