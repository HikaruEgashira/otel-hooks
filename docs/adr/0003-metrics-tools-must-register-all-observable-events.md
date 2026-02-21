# ADR-0003: metrics ツールは観測可能な全イベントに hook を登録する

## ステータス
採用

## コンテキスト
Copilot/Kiro は payload adapter 側で複数イベントを `metrics` 化できるが、設定登録が終端イベントのみだと実際には十分なイベントが流れない。

## 決定
`metrics` サポートのツールは、観測可能な全イベントへ `otel-hooks hook` を登録する。

- Copilot: `userPromptSubmitted`, `preToolUse`, `postToolUse`, `sessionEnd`
- Kiro: `userPromptSubmit`, `preToolUse`, `postToolUse`, `stop`

`is_hook_registered` は「全イベントに登録済み」を充足条件とする。

## 影響
- `status` と実際の観測能力が一致する。
- 終端イベント依存を排除し、prompt/tool/session の metrics 欠落を防ぐ。
- `preToolUse/postToolUse` の衝突を避けるため、hook 実行時に `source_tool` ヒントを付与して adapter 判定を安定化する。
