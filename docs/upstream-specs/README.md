# Upstream Specs

各サポートツールの公式Hooks仕様のスナップショット。
差分検知により、上流の仕様変更を追跡する。

## ファイル一覧

| File | Source | Snapshot |
|------|--------|----------|
| [claude.md](claude.md) | https://code.claude.com/docs/en/hooks | 2026-04-13 |
| [cursor.md](cursor.md) | https://cursor.com/ja/docs/hooks | 2026-04-04 |
| [codex.md](codex.md) | https://developers.openai.com/codex/config-reference | 2026-04-04 |
| [opencode.md](opencode.md) | https://opencode.ai/docs/plugins/ | 2026-04-04 |
| [gemini.md](gemini.md) | https://geminicli.com/docs/hooks/ | 2026-04-04 |
| [cline.md](cline.md) | https://docs.cline.bot/customization/hooks | 2026-04-04 |
| [copilot.md](copilot.md) | https://docs.github.com/en/copilot/reference/hooks-configuration | 2026-04-04 |
| [kiro.md](kiro.md) | https://kiro.dev/docs/cli/hooks/ | 2026-04-04 |

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
