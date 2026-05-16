import yfinance as yf    # インターネットから株価データを取得するライブラリ
import pandas as pd      # データを表形式で計算しやすくするライブラリ
import requests           # Discordなどの外部サービスに通信を送るライブラリ

# --- 1. 設定：DiscordのURL ---
# ここにご自身のDiscordウェブフックURLを貼り付けます
WEBHOOK_URL = "https://discord.com/api/webhooks/1504387094896705577/l7k3I5K2yyo2St0unNr1L6b72620PHfV3cZdjTe-d6qtmM93-egFFDVG5WaCWkxbJpZY" 

# --- 2. 設定：アラートを出すしきい値 ---
TH_RSI_HIGH = 70       # RSIが70以上なら「過熱（上がりすぎ）」と判断
TH_RSI_LOW = 30        # RSIが30以下なら「底打ち（売られすぎ）」と判断
TH_DEV_ABS = 7.0       # 25日移動平均線から7%以上離れたら「異常な急変」と判断
TH_VIX = 25.0          # VIX指数（恐怖指数）が25を超えたら「市場パニック」と判断
TH_JGB_DROP = -0.5     # 国債価格が前日比0.5%以上下がったら「金利急騰」と判断

def send_alert(messages):
    """異常を検知した時にDiscordへメッセージを飛ばす関数"""
    content = "【⚠️市場警戒アラート】\n" + "\n".join(messages)
    requests.post(WEBHOOK_URL, json={"content": content})

def check_stock(ticker_symbol, name):
    """日経平均やS&P500の数値を計算してチェックする関数"""
    # 過去2ヶ月分のデータを取得
    df = yf.Ticker(ticker_symbol).history(period="2mo")
    if df.empty: return [] # データが空なら何もしない
    
    close = df['Close'] # 終値（その日の最後の価格）を取り出す
    
    # 25日移動平均乖離率の計算
    ma25 = close.rolling(window=25).mean() # 直近25日間の平均を出す
    dev = ((close.iloc[-1] - ma25.iloc[-1]) / ma25.iloc[-1]) * 100 # 平均から何%離れているか
    
    # RSI (14日) の計算（過熱感を見る指標）
    delta = close.diff() # 前日との差分を出す
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean() # 上がった分の平均
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean() # 下がった分の平均
    rsi = 100 - (100 / (1 + (gain / loss))).iloc[-1]
    
    res = [] # 異常があればここにメッセージを貯める
    if rsi >= TH_RSI_HIGH: res.append(f"・{name} RSI過熱: {rsi:.1f}")
    if rsi <= TH_RSI_LOW:  res.append(f"・{name} RSI底打ち: {rsi:.1f}")
    if abs(dev) >= TH_DEV_ABS: res.append(f"・{name} 25日乖離率: {dev:.1f}%")
    return res

# --- メインの処理（ここから実行されます） ---
alerts = []

try:
    # 1. 日経平均のチェックを実行
    alerts.extend(check_stock("^N225", "日経平均"))
    
    # 2. S&P500のチェックを実行
    alerts.extend(check_stock("^GSPC", "S&P500"))
    
    # 3. VIX（恐怖指数）のチェック
    vix_df = yf.Ticker("^VIX").history(period="1d")
    if not vix_df.empty:
        vix = vix_df['Close'].iloc[-1]
        if vix >= TH_VIX:
            alerts.append(f"・VIX(恐怖)指数上昇: {vix:.1f}")

    # 4. 日本国債ETFのチェック（財政不安・金利上昇の監視）
    jgb_etf = yf.Ticker("2561.T").history(period="2d") # 直近2日分を取得
    if len(jgb_etf) >= 2:
        # 前日比で何%価格が動いたかを計算
        change = ((jgb_etf['Close'].iloc[-1] - jgb_etf['Close'].iloc[-2]) / jgb_etf['Close'].iloc[-2]) * 100
        if change <= TH_JGB_DROP: # 価格が大きく下がっていたら
            alerts.append(f"・日本国債ETF急落(金利上昇リスク): {change:.2f}%")

except Exception as e:
    # 何かエラーが起きても止まらずに、エラー内容だけ表示する
    print(f"エラー発生: {e}")

# 通知の実行
if alerts:
    send_alert(alerts) # 貯まったアラートがあれば送信
    print("異常を検知し通知を送りました。")
else:
    print("全ての指標は正常範囲内です。")
