# 英和辞典Extra — 第1段階

静的HTMLで動く学習用英和辞典サイトです。現在は `immaculate`、`mess`、`post` の3語を収録しています。

## 実装済み

- トップページ
- 単語別ページ
- 共通CSS・JavaScript
- 英単語・日本語訳・構文の検索
- アルファベット索引
- 頻度フィルター
- 日本語の表示／非表示
- 語義ごとの習得チェック（ブラウザ内保存）
- スマートフォン・印刷対応
- JSONから全ページと検索索引を生成するビルドスクリプト

## ローカル確認

ファイルを直接開いても閲覧できます。Webサーバーで確認する場合は、プロジェクト直下で次を実行してください。

```bash
python -m http.server 8000
```

ブラウザで `http://localhost:8000/` を開きます。

## 新しい単語を手動追加する方法

1. `content/` に既存ファイルを参考にした `<word>.json` を追加します。
2. 次を実行します。

```bash
python scripts/build_site.py
```

3. `index.html`、`words/`、`data/search-index.json` が再生成されます。

## GitHub Pagesで公開

1. このフォルダーの中身をGitHubリポジトリへコミットします。
2. GitHubの `Settings` → `Pages` を開きます。
3. `Deploy from a branch` を選択します。
4. 公開ブランチを `main`、フォルダーを `/ (root)` に設定します。

`.nojekyll` を含めているため、そのまま静的サイトとして公開できます。

## 次段階

Notion APIから完成版ページを取得し、JSON生成・ビルド・GitHubへの反映を自動化する構成へ拡張できます。
