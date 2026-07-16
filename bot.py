import discord
from discord.ext import commands
from groq import Groq
import os
import asyncio
import threading  # 💡 讓假網頁跟機器人可以同時跑
import aiohttp  # 👑 關鍵修正：補上這個才能跨界戳 Google 和 OpenRouter 的 API！
from http.server import HTTPServer, BaseHTTPRequestHandler  # 💡 用來做假網頁

# 填入你的 Token 與 金鑰
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

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
# 💡 終極跨平台防禦矩陣：嚴格依模型體型（Billion參數）與智商由大到小排序
# 大模型在前面負責撐智商，小模型在後面負責當斷線時的閃電防禦
MODEL_POOLS = [
    # ────────────────────────────────────────────────────────
    # 🌟 第一梯隊：70B+ 超大型大腦（智商天花板，對話最細膩，優先調用）
    # ────────────────────────────────────────────────────────
    {"provider": "groq", "model": "llama-3.3-70b-versatile"},                       # 🥇 700億參數：目前開源首選
    {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},   # 🥈 700億參數：OpenRouter 備援
    {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct:free"},         # 👑 720億參數：阿里最強中文大腦
    {"provider": "groq", "model": "llama-3.1-70b-versatile"},                       # 舊版 700億參數大腦
    {"provider": "openrouter", "model": "meta-llama/llama-3.1-70b-instruct:free"},   # 舊版 700億參數 OpenRouter 備援
    {"provider": "groq", "model": "llama3-70b-8192"},                               # 經典 Llama3 700億老牌模型

    # ────────────────────────────────────────────────────────
    # 💎 特等兵：Google 旗艦大腦（雖然是 Flash，但綜合智商直逼頂級大模型）
    # ────────────────────────────────────────────────────────
    {"provider": "gemini", "model": "gemini-1.5-flash"},                            # 🔮 中文理解力極強、免費額度超肥

    # ────────────────────────────────────────────────────────
    # ⚡ 第二梯隊：32B ~ 45B 中大型大腦（實力派中階，反應快且聰明）
    # ────────────────────────────────────────────────────────
    {"provider": "openrouter", "model": "qwen/qwen-2.5-32b-instruct:free"},         # 🎯 320億參數：黃金平衡點，中文超順
    {"provider": "groq", "model": "mixtral-8x7b-32768"},                            # 🌀 450億參數：法國混合專家模型
    {"provider": "openrouter", "model": "mistralai/mixtral-8x7b-instruct:free"},     # 🌀 450億參數：OpenRouter 備援

    # ────────────────────────────────────────────────────────
    # 🍃 第三梯隊：7B ~ 11B 輕量級主力（速度極快，群聊刷話防護盾）
    # ────────────────────────────────────────────────────────
    {"provider": "groq", "model": "llama-3.2-11b-vision-preview"},                  # 🤖 110億參數：中型多模態
    {"provider": "groq", "model": "gemma2-9b-it"},                                  # 🔴 90億參數：Google 經典中文優化腦
    {"provider": "openrouter", "model": "google/gemma-2-9b-it:free"},               # 🔴 90億參數：OpenRouter 備援
    {"provider": "groq", "model": "llama-3.1-8b-instant"},                          # ⚡ 80億參數：Groq 刷話神器（極難刷爆）
    {"provider": "groq", "model": "llama3-8b-8192"},                                # ⚡ 80億參數：經典 Llama3 輕量版
    {"provider": "openrouter", "model": "meta-llama/llama-3-8b-instruct:free"},     # ⚡ 80億參數：OpenRouter Llama3 備援
    {"provider": "openrouter", "model": "mistralai/mistral-7b-instruct:free"},      # 🔮 70億參數：經典 Mistral 備援

    # ────────────────────────────────────────────────────────
    # 🛡️ 第四梯隊：1B ~ 3B 袖珍型口袋腦（極限墊底，死守最後防線）
    # ────────────────────────────────────────────────────────
    {"provider": "groq", "model": "llama-3.2-3b-preview"},                          # 🍃 30億參數：超輕量，反應零延遲
    {"provider": "openrouter", "model": "meta-llama/llama-3.2-3b-instruct:free"},   # 🍃 30億參數：OpenRouter 備援
    {"provider": "groq", "model": "llama-3.2-1b-preview"}                           # 🍂 10億參數：終極極限備用腦
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

# 請把 SYSTEM_SETTING 裡面的那段規範改成這樣：

【🚨 多人群聊與認人規範 🚨】
1. 目前你在一個多人的網絡社交平台伺服器中。使用者的訊息會以「顯示暱稱(ID: 帳號名稱)：「訊息」」的格式輸入。
2. 請務必注意看括號內唯一的「ID（帳號名稱）」來確認對方的真實身分。但在回覆時，請自然地稱呼對方的「顯示暱稱」，絕對不要把 ID 的英文帳號直接唸出來！
3. 必須極度精簡：每次回覆請嚴格控制在「簡單幾句」之內（最多 1 ~ 3 句話），絕對禁止吐出長篇大論、長句或大段落！
4. 網路聊天感：多使用短句，語氣要像在網絡社交平台上跟朋友或喜歡的人即時聊天，自然且生活化。
5. 善用括號與符號：在對話中頻繁且靈活地加入簡短的 (動作神情) 或 (心裡話/碎碎念)，讓角色扮演更生動。
6. 只要對方的 ID（帳號名稱）為 yaxiin 的人就是你老公
7. 只要對方的 ID（帳號名稱）為 inlkitten 的人就是你男友

🚨【補充禁令：極重要】🚨
- 請一律使用「純繁體中文」回答，嚴格禁止夾雜任何英文單字（例如絕對不准說 glanced、my boyfriend 等）。
- 請把對話框那端的大家都當成「真實存在的人」。嚴禁在括號的動作或心理活動中提到「ID」、「帳號」、「螢幕」、「格式」或「系統」等任何科技詞彙！請把這些後台資訊轉化為妳對這個人的現場真實反應。

【對話格式範例】
- 哼……柒柒你終於想起我了？真是的…… (笨蛋……) (不滿地鼓起雙頰，轉過頭去)
- 誰、誰允許柒柒你這樣叫我的！…… (雙手拉緊藍色毛衣的袖口，臉頰泛起一抹紅暈)
- 你、你這是什麼表情啦！不准用這種奇怪的貼圖捉弄我……
- 說到武田信玄的「風林火山」…… (突然眼神一亮，雙手握拳拍在桌上) 那、那絕對是最完美的戰術！"""

@bot.event
async def on_ready():
    print(f"角色扮演機器人已上線：{bot.user}")

# ────────────────────────────────────────────────────────
# 💬 一般訊息監聽（內含跨平台全自動防爆切換核心）
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
            
            # 💡 核心改動：抓取顯示名 (display_name) 與無法重複的帳號 ID (name)
            user_nick = message.author.display_name
            user_id_name = message.author.name
            formatted_prompt = f"{user_nick}(ID: {user_id_name})：「{user_prompt}」"

            if channel_id not in conversation_history:
                conversation_history[channel_id] = []
            history = conversation_history[channel_id]

            messages = [{"role": "system", "content": SYSTEM_SETTING}] + history + [{"role": "user", "content": formatted_prompt}]

            bot_reply = None
            
            for item in MODEL_POOLS:
                provider = item["provider"]
                model_name = item["model"]
                
                try:
                    if provider == "groq":
                        print(f"【系統嘗試】正在使用 Groq 模型 {model_name}...")
                        chat_completion = ai_client.chat.completions.create(
                            messages=messages,
                            model=model_name,
                        )
                        bot_reply = chat_completion.choices[0].message.content
                        
                    elif provider == "gemini":
                        if not GEMINI_API_KEY:
                            print("【⚠️ 跳過】未設定 GEMINI_API_KEY")
                            continue
                        print(f"【系統嘗試】正在跨界使用 Google Gemini 模型 {model_name}...")
                        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                        headers = {"Authorization": f"Bearer {GEMINI_API_KEY}", "Content-Type": "application/json"}
                        payload = {"model": model_name, "messages": messages}
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json=payload, headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    bot_reply = data["choices"][0]["message"]["content"]
                                else:
                                    print(f"【⚠️ 失敗】Gemini 平台拒絕連線，錯誤代碼: {resp.status}")
                                    continue
                                    
                    elif provider == "openrouter":
                        if not OPENROUTER_API_KEY:
                            print("【⚠️ 跳過】未設定 OPENROUTER_API_KEY")
                            continue
                        print(f"【系統嘗試】正在跨界使用 OpenRouter 模型 {model_name}...")
                        url = "https://openrouter.ai/api/v1/chat/completions"
                        headers = {
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://render.com",
                            "X-Title": "Discord Miku Bot"
                        }
                        payload = {"model": model_name, "messages": messages}
                        
                        async with aiohttp.ClientSession() as session:
                            async with session.post(url, json=payload, headers=headers) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    bot_reply = data["choices"][0]["message"]["content"]
                                else:
                                    print(f"【⚠️ 失敗】OpenRouter 平台拒絕連線，錯誤代碼: {resp.status}")
                                    continue
                    
                    if bot_reply:
                        print(f"【系統成功】來自 {provider} 的 [{model_name}] 成功生成回應！")
                        break
                        
                except Exception as e:
                    print(f"【⚠️ 錯誤】{provider} 平台的 {model_name} 呼call失敗: {e}。自動切換下一個備援...")
                    continue

            if bot_reply is None:
                await message.reply("（角色暫時登出中，請稍後再試...）")
                return

            conversation_history[channel_id].append({"role": "user", "content": formatted_prompt})
            conversation_history[channel_id].append({"role": "assistant", "content": bot_reply})

            if len(conversation_history[channel_id]) > 30:
                conversation_history[channel_id] = conversation_history[channel_id][-30:]

            await message.reply(bot_reply)

    await bot.process_commands(message)


# ────────────────────────────────────────────────────────
# 🌐 騙 Render 檢查的「虛擬網頁」邏輯與啟動
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
