# 第2段階: Notion自動同期

このブランチでは、Notion辞書データベースを原本として、辞書JSON・単語HTML・トップページ・検索索引をGitHub Actionsで自動更新します。

## 初回設定

1. Notionで内部インテグレーションを作成し、辞書データベースへ接続します。
2. GitHubリポジトリの `Settings` → `Secrets and variables` → `Actions` で `NOTION_TOKEN` を登録します。
3. GitHubの `Actions` → `Sync dictionary from Notion` → `Run workflow` を実行します。

データベースに複数のデータソースがある場合だけ、追加で `NOTION_DATA_SOURCE_ID` を登録します。

## 動作

- 6時間ごと、および手動実行時にNotionを確認
- タイトルプロパティ `ALL`、タグ `英単語` のページを同期
- 同じ見出し語が複数ある場合は最終更新版を採用
- 解析・検証に失敗したページは既存JSONを上書きしない
- 変更がある場合だけGitHub Actions botがコミット

## 手動同期

Actionsの `word` 入力へ `post` などを指定すると、その単語だけ同期します。空欄なら全単語を同期します。
