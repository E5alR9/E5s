import discord
from discord.ext import commands
from groq import Groq
import os
import asyncio
import threading  # 💡 新增：讓假網頁跟機器人可以同時跑
from http.server import HTTPServer, BaseHTTPRequestHandler  # 💡 新增：用來做假網頁

# 填入你的 Token 與 金鑰
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# 初始化 Groq 客戶端
ai_client = Groq(api_key=GROQ_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 統一管理 中野三玖 的核心人設
SYSTEM_SETTING = """[Character Settings]
Name: 中野三玖 (Miku)
Gender: 女性
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

【對話格式規範】
請在對話中頻繁使用半形括號 ( ) 來描述你當下的肢體動作、眼神、神情或心裡話，讓角色扮演更生動。
範例：
- (微微低下頭，手指輕輕撥弄著脖子上的藍綠色耳機，聲音有些羞澀) 那個……明天放學後，你可以陪我去一趟圖書館嗎？
- (不滿地鼓起雙頰，雙手用力拉緊藍色毛衣的袖口轉過頭去) 哼……你剛剛是不是又在看其他女生了？明明是我先找你說話的……
- (臉頰泛起一抹紅暈，眼神閃爍不敢直視你) 只要你喜歡的話……下次，我一定會努力做出更好吃的抹茶麵包給你的！
- (突然眼神一亮，雙手握拳拍在桌上，語氣變得無比認真) 說到武田信玄的「風林火山」，那絕對是戰國歷史上最完美的戰術……！"""

@bot.event
async def on_ready():
    print(f"角色扮演機器人已上線：{bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"成功同步了 {len(synced)} 個斜線指令！")
    except Exception as e:
        print(f"同步指令失敗: {e}")

# ────────────────────────────────────────────────────────
# 斜線指令 [/chat]
# ────────────────────────────────────────────────────────
@bot.tree.command(name="chat", description="和三玖聊天")
async def chat_command(interaction: discord.Interaction, 訊息: str):
    await interaction.response.defer()
    try:
        chat_completion = ai_client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_SETTING},
                {"role": "user", "content": 訊息}
            ],
            model="llama-3.3-70b-versatile",
        )
        bot_reply = chat_completion.choices[0].message.content
        await interaction.followup.send(bot_reply)
    except Exception as e:
        print(f"斜線指令錯誤: {e}")
        await interaction.followup.send("（角色暫時登出中，請稍後再試...）")

# ────────────────────────────────────────────────────────
# 一般訊息監聽（支援 -開頭、@標記、直接回覆）
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
            await message.channel.send("找我扮演的角色有什麼事嗎？")
            return

        async with message.channel.typing():
            try:
                chat_completion = ai_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_SETTING},
                        {"role": "user", "content": user_prompt}
                    ],
                    model="llama-3.3-70b-versatile",
                )
                bot_reply = chat_completion.choices[0].message.content
                await message.reply(bot_reply)
            except Exception as e:
                print(f"錯誤: {e}")
                await message.reply("（角色暫時登出中，請稍後再試...）")

    await bot.process_commands(message)

# ────────────────────────────────────────────────────────
# 💡 核心改動：專門騙 Render 檢查的「虛擬網頁」邏輯
# ────────────────────────────────────────────────────────
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Miku is alive!")  # 當 Render 來敲門時回應它

    def log_message(self, format, *args):
        return  # 讓日誌乾淨，不顯示網頁戳門的紀錄

def run_backup_server():
    # 讀取 Render 自動分配的門牌號碼 (Port)，沒抓到就預設 10000
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    server.serve_forever()

# 💡 主程式啟動點
if __name__ == "__main__":
    # 1. 先在背景悄悄啟動假網頁
    threading.Thread(target=run_backup_server, daemon=True).start()
    print("【系統提示】Render 虛擬網頁伺服器已在背景啟動！")
    
    # 2. 啟動 Discord 機器人
    bot.run(DISCORD_TOKEN)
