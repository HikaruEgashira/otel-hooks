# ADR-0002: OpenCode plugin パスは `.opencode/plugins` のみに限定する

## ステータス
採用

## コンテキスト
OpenCode plugin の接続自動化で、公式探索パスは `.opencode/plugins/` である。
一方で過去実装には `opencode/plugin/` へのレガシーフォールバックが残り、設定の意味論が二重化していた。

## 決定
`otel-hooks` の OpenCode 連携は `.opencode/plugins/otel-hooks.js` のみをサポートする。
`opencode/plugin/otel-hooks.js` は非対応とし、読み込み・移行・削除の互換処理は実装しない。

## 根拠
- 接続自動化の目的は「OpenCode が自動で探索する正規パス」に一本化すること。
- レガシー互換を残すと、どのパスが有効設定かが利用者と実装で不一致になりやすい。

## 影響
- 実装責務が単純化され、`OpenCodeConfig.settings_path` の意味が明確になる。
- 既存の `opencode/plugin/otel-hooks.js` は自動利用されないため、必要に応じて手動移設が必要となる。
