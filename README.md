# LeadGenius Design Suite

Fulfill株式会社のAIサービス群（LeadGenius AI / AIO Insight / BeginAI）を支える  
**リード収集 + デザイン自動調査 + LP生成** の統合ツールキット。

---

## 全体アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                    LeadGenius Design Suite                       │
├─────────────────┬──────────────────────┬────────────────────────┤
│  lead_scraper/  │  design_research/    │  design_studio/        │
│                 │                      │                        │
│  Scrapling      │  Serper → Firecrawl  │  Design Studio (React) │
│  Spider で      │  → Gemini で         │  参考URL → デザインDNA │
│  企業情報収集   │  デザイン自動収集    │  → LP生成              │
│       ↓         │       ↓              │                        │
│  Gemini で      │  ストック +          │  LP Builder (React)    │
│  スコアリング   │  変化検知 +          │  セクション分割編集    │
│       ↓         │  スクリーンショット  │  ドラッグ並び替え      │
│  Resend で      │       ↓              │  AI修正指示            │
│  メール送信     │  トレンドレポート    │  HTMLダウンロード      │
└─────────────────┴──────────────────────┴────────────────────────┘
```

---

## クイックスタート

### 1. インストール

```bash
pip install "scrapling[all]" google-genai requests resend
scrapling install
```

### 2. APIキー設定

```bash
# 必須
export GEMINI_API_KEY="your-key"           # https://aistudio.google.com

# デザイン調査に必要
export SERPER_API_KEY="your-key"           # https://serper.dev （無料2,500q）
export FIRECRAWL_API_KEY="fc-your-key"     # https://firecrawl.dev （無料枠あり）

# リード送信に必要
export RESEND_API_KEY="your-key"           # https://resend.com
export SENDER_EMAIL="sales@fulfill-corp.jp"

# 通知（オプション）
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

### 3. 動かす

```bash
# デザイン調査を1回実行
cd design_research
python design_researcher_v2.py

# リード収集パイプライン（Dry Run）
cd lead_scraper
python pipeline.py --targets targets_sample.json --dry-run

# React UI（Claude Artifact / Next.js に配置）
# → design_studio/lp_builder.jsx
# → design_studio/design_studio.jsx
```

---

## モジュール詳細

### 📁 lead_scraper/ — リード収集パイプライン

LeadGenius AI の最上流。企業Webサイトからリード情報を自動収集し、  
Geminiでスコアリング＆メール生成、Resendで送信する。

| ファイル | 役割 |
|----------|------|
| `lead_spider.py` | Scrapling Spider。企業サイトから社名・代表者・電話・メール・免許番号等を抽出 |
| `lead_enricher.py` | Gemini APIでスコアリング（0-100）+ パーソナライズドメール生成 |
| `pipeline.py` | 収集→分析→送信→エクスポートの統合CLI |
| `targets_sample.json` | ターゲットURLサンプル |

```bash
# 使い方
python pipeline.py --targets targets.json --dry-run     # テスト
python pipeline.py --targets targets.json --min-score 50 # 本番
```

**Scrapling活用ポイント:**
- `StealthyFetcher`: Cloudflare等で保護されたサイトも取得可能
- `DynamicFetcher`: SPA（React/Next.js）のJSレンダリング後のDOMを取得
- `adaptive=True`: サイトデザイン変更後も要素を自動再検出

---

### 📁 design_research/ — デザイン自動調査 & ストック

おしゃれなWebデザインを毎日自動で収集・分析・ストックする。

| ファイル | 役割 |
|----------|------|
| `design_researcher_v2.py` | メインパイプライン（5ステップ） |
| `design_monitor.py` | 📸 スクリーンショット + 🔄 変化検知 |
| `scheduler_v2.py` | cron / systemd / 常駐スケジューラー |
| `config.json` | ビッグキーワード・API設定・フィルタ |

**パイプラインフロー（毎日AM3:00自動実行）:**

```
Step 1: Gemini → スモールKW自動生成（日次ローテーション）
Step 2: Serper.dev → Google検索TOP10 URL取得
Step 3: Firecrawl Branding → カラー/フォント/レイアウト構造化抽出
        Gemini → 美的スタイル名・スコア・タグ等の補足分析
        📸 スクリーンショット自動保存
Step 4: トレンドレポート生成
Step 5: 既存サイト変化検知 → Discord/Slack通知
```

```bash
# 手動実行
python design_researcher_v2.py

# 変化検知のみ
python design_researcher_v2.py --check-changes

# スクリーンショット
python design_researcher_v2.py --screenshot https://stripe.com

# 毎日自動実行の設定
python scheduler_v2.py --setup-cron --hour 3

# 今すぐ1回実行
python scheduler_v2.py --run-now
```

**出力:**
```
design_stock_v2/
├── index.json                    # 全エントリのインデックス
├── {hash}.json                   # 各サイトの詳細分析データ
├── trend_YYYYMMDD.json           # トレンドレポート
├── screenshots/                  # スクリーンショット画像
│   ├── {hash}_{timestamp}.png
│   └── {hash}_{timestamp}_thumb.png
└── change_history/               # 変化検知履歴
    └── {hash}_{timestamp}.json
```

---

### 📁 design_studio/ — LP生成 & 編集UI

ストックしたデザインを参考に、AIでLPを生成・編集する React UI。

| ファイル | 用途 |
|----------|------|
| `design_studio.jsx` | 参考URL入力 → デザインDNA抽出 → LP一括生成 |
| `lp_builder.jsx` | セクション分割編集 + ドラッグ並び替え + AI修正 |

**Design Studio（デザインDNA抽出 → LP一括生成）:**
1. おしゃれなサイトのURLを1-5件入力
2. Claude APIがデザインDNA（カラー・フォント・レイアウト）を分析
3. そのDNAを基にオリジナルLPを日本語で生成
4. プレビュー / コード表示 / HTMLダウンロード

**LP Builder（セクション分割編集）:**
1. 8セクション（ヒーロー〜フッター）を個別に生成
2. 前セクションのスタイルを引き継いで統一感を維持
3. セクションごとにAI修正指示（「背景を暗く」「CTAを大きく」等）
4. ドラッグ＆ドロップで構成変更
5. セクション複製・削除
6. フルプレビュー / HTMLダウンロード

**使い方:** Claude Artifact として開くか、Next.js の `app/` に配置

---

## API & MCP 連携一覧

| サービス | 用途 | 無料枠 | 月額目安 |
|----------|------|--------|----------|
| **Gemini Flash** | KW生成・分析・スコアリング・メール生成 | 1日1,500req | $0 |
| **Serper.dev** | Google検索結果取得 | 2,500q永久 | $0 |
| **Firecrawl** | デザインDNA抽出・スクリーンショット | 500クレジット | $0〜$16 |
| **Scrapling** | ステルススクレイピング・フォールバック | OSS無料 | $0 |
| **Resend** | メール送信 | 100通/日 | $0 |
| **Claude API** | LP生成・セクション編集（React UI内） | — | 使用量次第 |

**MCP サーバー設定（Claude Desktop / Cursor）:**

```json
{
  "mcpServers": {
    "ScraplingServer": {
      "command": "scrapling",
      "args": ["mcp"]
    },
    "firecrawl-mcp": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "fc-YOUR_KEY" }
    },
    "serper": {
      "command": "npx",
      "args": ["-y", "serper-mcp-server"],
      "env": { "SERPER_API_KEY": "YOUR_KEY" }
    }
  }
}
```

---

## 今後のロードマップ

- [x] Supabase連携（ストック永続化 + pgvectorで類似デザイン検索）
- [ ] Vercelデプロイ（ダッシュボード + LP Builder をWeb公開）
- [ ] n8n / Claude Cowork 連携（完全自動化）
- [ ] 関西不動産ターゲットリストで実際にリード収集実行
- [ ] AIO Insight LP のリニューアル（ストックデザインを参考に）
- [ ] BeginAI ワークショップ教材としてのパッケージ化

---

## 🔍 Supabase連携（ベクトル検索 + 永続化）

デザインストックをSupabase PostgreSQL + pgvectorに永続化し、
自然言語で類似デザインを検索できます。

### セットアップ

```bash
pip install supabase google-genai

# 1. スキーマSQL生成
cd design_research
python supabase_store.py --init
# → supabase_schema.sql が生成される
# → Supabase Dashboard > SQL Editor で実行

# 2. 環境変数設定
export SUPABASE_URL="https://xxxxx.supabase.co"
export SUPABASE_KEY="eyJhbG..."

# 3. ローカルストック → Supabase同期
python supabase_store.py --sync
```

### 類似デザイン検索

```bash
# 自然言語で検索
python supabase_store.py --search "ダーク ミニマル SaaS"
python supabase_store.py --search "不動産 信頼感 グリーン系"
python supabase_store.py --search "stripe.comのような洗練されたデザイン"

# 特定エントリに類似したデザインを検索
python supabase_store.py --similar-to abc123def456

# 統計表示
python supabase_store.py --stats
```

### 仕組み

```
デザインエントリ
  ↓ テキスト化
  「デザインスタイル: ミニマル・テック
   カラー: primary #635BFF, background #0A2540
   フォント: Söhne
   タグ: ミニマル, グラデーション, ダーク」
  ↓ Gemini text-embedding-004（768次元）
  ↓ pgvector に保存
  ↓ HNSW インデックスで高速近似検索
```

毎日のデザイン調査パイプライン実行時に自動的にSupabaseにも同期されます。

---

## プロジェクト構成

```
leadgenius-design-suite/
├── README.md                          # このファイル
├── .env.example                       # 環境変数テンプレート
│
├── lead_scraper/                      # リード収集
│   ├── lead_spider.py                 # Scrapling Spider
│   ├── lead_enricher.py               # Gemini スコアリング
│   ├── pipeline.py                    # 統合パイプライン
│   └── targets_sample.json            # ターゲットURL例
│
├── design_research/                   # デザイン自動調査
│   ├── design_researcher_v2.py        # メインパイプライン
│   ├── design_monitor.py              # スクリーンショット + 変化検知
│   ├── scheduler_v2.py                # スケジューラー
│   └── config.json                    # 設定
│
├── design_studio/                     # LP生成UI
│   ├── design_studio.jsx              # デザインDNA → LP生成
│   └── lp_builder.jsx                 # セクション分割編集
│
└── docs/                              # ドキュメント
    └── api_comparison.md              # API/MCP調査結果
```
