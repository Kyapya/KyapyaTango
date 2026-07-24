# Notion webhook Worker

Notionの変更通知を検証し、`.github/workflows/sync-notion.yml`を起動するCloudflare Workerです。

## エンドポイント

- `GET /health` または `GET /`: 設定状態の確認
- `POST /notion-webhook` または `POST /`: Notion Webhookの受信

## 必要なWorker Secrets

- `GITHUB_TOKEN`: `Kyapya/KyapyaTango`だけを対象にし、Repository permissionsの`Actions: Read and write`を付けたfine-grained personal access token
- `NOTION_VERIFICATION_TOKEN`: Notionが購読作成時に一度だけ送る`verification_token`

トークン値はリポジトリや通常の環境変数へ書かず、Cloudflareの`Variables and Secrets`で種類を`Secret`にして登録します。

## Cloudflare Dashboardでのデプロイ

1. `Workers & Pages`からWorkerを作成し、このGitHubリポジトリを接続します。
2. Root directoryを`cloudflare/notion-webhook`に設定します。
3. Deploy commandを`npx wrangler deploy`に設定してデプロイします。
4. Workerの`Settings`→`Variables and Secrets`で`GITHUB_TOKEN`をSecretとして登録します。
5. `https://<worker名>.<subdomain>.workers.dev/health`を開き、`githubToken`が`true`であることを確認します。

## Notion Webhookの初回認証

1. Notionの対象コネクションでWebhook購読を作成します。
2. URLには`https://<worker名>.<subdomain>.workers.dev/notion-webhook`を指定します。
3. イベントは次を選択します。
   - `page.created`
   - `page.content_updated`
   - `page.properties_updated`
   - `page.deleted`
   - `page.undeleted`
   - `page.moved`
   - `data_source.content_updated`
   - `data_source.schema_updated`
4. CloudflareのWorkerログを開き、`kind: notion_webhook_verification`のログにある`verification_token`をコピーします。
5. NotionのVerify画面へ貼り付けます。
6. 同じ値をCloudflareの`NOTION_VERIFICATION_TOKEN` Secretとして登録し、デプロイします。
7. `/health`で`notionVerificationToken`も`true`になったことを確認します。

## 動作確認

Notionの辞書データベースでテスト用の変更を保存します。Cloudflareログに`github_workflow_dispatched`が出て、GitHub Actionsの`Sync dictionary from Notion`が起動すれば成功です。

Notionのコネクションは辞書データベースだけにアクセスさせてください。これにより、別ページの更新でサイト同期が起動するのを防げます。

## ローカルテスト

```bash
npm install
npm test
```
