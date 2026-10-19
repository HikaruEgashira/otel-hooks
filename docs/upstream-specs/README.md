# Upstream Specs

各サポートツールの公式Hooks仕様のスナップショット。
差分検知により、上流の仕様変更を追跡する。

## ファイル一覧

| File | Source | Snapshot |
|------|--------|----------|
| [claude.md](claude.md) | https://code.claude.com/docs/en/hooks | 2026-10-13 |
| [cursor.md](cursor.md) | https://cursor.com/ja/docs/hooks | 2026-10-13 |
| [codex.md](codex.md) | https://learn.chatgpt.com/docs/config-file/config-reference | 2026-10-13 |
| [opencode.md](opencode.md) | https://opencode.ai/docs/plugins/ | 2026-10-13 |
| [gemini.md](gemini.md) | https://geminicli.com/docs/hooks/ | 2026-06-16 |
| [cline.md](cline.md) | https://docs.cline.bot/sdk/plugins | 2026-10-13 |
| [copilot.md](copilot.md) | https://docs.github.com/en/copilot/reference/hooks-configuration | 2026-10-13 |
| [kiro.md](kiro.md) | https://kiro.dev/docs/hooks/ | 2026-10-13 |

## 検査対象

`UPSTREAM_URLS` に登録された全ツールについて、上流ドキュメントの
イベント名と payload field 名をスナップショットと比較する。追加・削除の
両方を検知する。チェッカーは仕様の差分を報告するだけで、ハンドラーコードの
生成やランタイム動作の変更は行わない。変更は必ずレビューしてから
スナップショットへ反映する。

## 差分検知の使い方

```bash
# 全ツールの公式ドキュメントとスナップショットの差分チェック
python scripts/check_upstream_specs.py

# 特定ツールのみ
python scripts/check_upstream_specs.py --tool claude
```

## 運用フロー

1. `scripts/check_upstream_specs.py` が公式ドキュメントを取得し、現在のスナップショットと比較
2. 差分があれば具体的な変更点を報告
3. 確認後、スナップショットを更新してコミット
