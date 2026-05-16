import yfinance as yf    # インターネットから株価データを取得するライブラリ
import pandas as pd      # データを表形式で計算しやすくするライブラリ
import requests           # Discordなどの外部サービスに通信を送るライブラリ

# --- 1. 設定：DiscordのURL ---
# ここにご自身のDiscordウェブフックURLを貼り付けます
WEBHOOK_URL = "https://discord.com/api/webhooks/1504387094896705577/l7k3I5K2yyo2St0unNr1L6b72620PHfV3cZdjTe-d6qtmM93-egFFDVG5WaCWkxbJpZY" 

# --- 2. 設定：【パターン1】通常アラートのしきい値 ---
TH_RSI_HIGH = 70        # RSIが70以上なら「過熱（上がりすぎ）」
TH_RSI_LOW = 30         # RSIが30以下なら「底打ち（売られすぎ）」
TH_DEV_ABS = 7.0        # 25日移動平均線から7%以上離れたら「異常な急変」
TH_VIX_NORMAL = 25.0    # VIX指数が25を超えたら「市場パニック」
TH_JGB_DROP = -0.5      # 国債価格が前日比0.5%以上下がったら「金利急騰」

# --- 3. 設定：【パターン2】ショック初動の緊急避難サイン（AND条件） ---
TH_DEV_LOW = -5.0        # 25日移動平均線乖離率がこの数値以下
TH_RSI_BEAR = 50.0       # RSIが50を下に割った瞬間
TH_VIX_CRITICAL = 28.0   # VIX指数（恐怖指数）がこの数値以上

def send_alert(title, messages, is_emergency=False):
    """警告メッセージを整形してDiscordへ飛ばす関数"""
    emoji = "🚨" if is_emergency else "⚠️"
    content = f"【{emoji}{title}】\n" + "\n".join(messages)
    requests.post(WEBHOOK_URL, json={"content": content})

def check_stock(ticker_symbol, name, vix_value):
    """1回のデータ取得で、パターン1とパターン2の両方を同時にチェックする関数"""
    # 過去2ヶ月分のデータを取得
    df = yf.Ticker(ticker_symbol).history(period="2mo")
    if df.empty: return [], [] # データが空なら何もしない
    
    close = df['Close'] # 終値を取り出す
    
    # 25日移動平均乖離率の計算
    ma25 = close.rolling(window=25).mean()
    dev = ((close.iloc[-1] - ma25.iloc[-1]) / ma25.iloc[-1]) * 100
    
    # RSI (14日) の計算
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    if loss.iloc[-1] == 0:
        rsi = 100 if gain.iloc[-1] > 0 else 50
    else:
        rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    
    normal_alerts = []
    emergency_alerts = []
    
    # ----------------------------------------------------
    # 判定A：【パターン1】通常の個別チェック
    # ----------------------------------------------------
    if rsi >= TH_RSI_HIGH:     normal_alerts.append(f"・{name} RSI過熱: {rsi:.1f}")
    if rsi <= TH_RSI_LOW:      normal_alerts.append(f"・{name} RSI底打ち: {rsi:.1f}")
    if abs(dev) >= TH_DEV_ABS: normal_alerts.append(f"・{name} 25日乖離率: {dev:.1f}%")
    
    # ----------------------------------------------------
    # 判定B：【パターン2】緊急避難のANDチェック
    # ----------------------------------------------------
    if dev <= TH_DEV_LOW and rsi < TH_RSI_BEAR and vix_value >= TH_VIX_CRITICAL:
        emergency_alerts.append(
            f"🔥 **{name}のトレンド崩壊（暴落初動の可能性）**\n"
            f"  ・25日乖離率: {dev:.1f}% (しきい値: {TH_DEV_LOW}%以下)\n"
            f"  ・RSI (14日): {rsi:.1f} (しきい値: {TH_RSI_BEAR}未満)\n"
            f"  ・現在のVIX: {vix_value:.1f} (しきい値: {TH_VIX_CRITICAL}以上)\n"
            f"※単なる一時的調整ではなく、大口のパニック売りのサインです。ポジション縮小の検討を推奨。"
        )
        
    return normal_alerts, emergency_alerts

# --- メインの処理 ---
normal_list = []
emergency_list = []

try:
    # 1. 先にVIX（恐怖指数）の現在の値を取得
    vix_df = yf.Ticker("^VIX").history(period="1d")
    vix_current = vix_df['Close'].iloc[-1] if not vix_df.empty else 0.0

    # パターン1用：VIX単体での上昇チェック
    if vix_current >= TH_VIX_NORMAL:
        normal_list.append(f"・VIX(恐怖)指数上昇: {vix_current:.1f} (基準: {TH_VIX_NORMAL})")

    # 2. 各市場のチェック（パターン1と2を同時に計算）
    if vix_current > 0:
        # 日経平均のチェック
        n225_normal, n225_emerg = check_stock("^N225", "日経平均", vix_current)
        normal_list.extend(n225_normal)
        emergency_list.extend(n225_emerg)
        
        # S&P500のチェック
        gspc_normal, gspc_emerg = check_stock("^GSPC", "S&P500", vix_current)
        normal_list.extend(gspc_normal)
        emergency_list.extend(gspc_emerg)

    # 3. パターン1用：日本国債ETFのチェック（金利上昇リスク）
    jgb_etf = yf.Ticker("2561.T").history(period="2d")
    if len(jgb_etf) >= 2:
        change = ((jgb_etf['Close'].iloc[-1] - jgb_etf['Close'].iloc[-2]) / jgb_etf['Close'].iloc[-2]) * 100
        if change <= TH_JGB_DROP:
            normal_list.append(f"・日本国債ETF急落(金利上昇リスク): {change:.2f}%")

except Exception as e:
    print(f"エラー発生: {e}")

# --- Discordへの通知判定 ---
# 通常アラートがあれば送信
if normal_list:
    send_alert("市場警戒アラート（個別指標）", normal_list, is_emergency=False)

# 緊急避難サインが揃っていれば、別メッセージで目立たせて送信
if emergency_list:
    send_alert("緊急避難アラート（ショック初動サイン）", emergency_list, is_emergency=True)

# ログ出力
if not normal_list and not emergency_list:
    print("すべての指標は正常範囲内です。")
else:
    print("条件に合致したアラートを通知しました。")
