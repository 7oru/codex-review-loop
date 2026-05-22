# codex-review-loop

Codex skill for P0/P1 repository review/fix loops with paired or batch `codex exec` runners.

中文：这是一个 Codex skill，用来让 Codex 对一个代码仓库做可重复的 review/fix 循环：只找真实的 P0/P1 问题，修复选中的问题或一组安全的批量问题，补回归测试，通过后提交，并把循环状态记录下来。

Recommended GitHub description:

```text
Codex skill for P0/P1 repository review/fix loops with paired or batch codex exec runners.
```

## 中文

### 这是什么

`codex-review-loop` 适合在一个仓库里反复做高信号的代码审查和修复。它不是普通 lint，也不是待办清单生成器。它的默认目标很窄：

- 只报告真实、可复现、有明确影响的 P0/P1 问题。
- review 阶段不改代码，只产出结论。
- fix 阶段只修选中的问题，尽量小改动。
- 修复时补或更新回归测试。
- 测试通过后把修复提交成 commit。
- 把每一轮结果写入 `review-loop.md`，方便后续继续。

### 什么时候用

适合：

- 发版前检查核心流程。
- 检查“本地一键安装/运行”是否真的可用。
- 大改动后找高优先级回归。
- 想让 Codex 连续跑几轮 review/fix，但又不想在当前聊天里无限循环。

不适合：

- 收集 P2/P3 优化建议。
- 做纯风格审查。
- 替代 CI、类型检查或人工设计评审。

### 安装

把仓库克隆到 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:7oru/codex-review-loop.git ~/.codex/skills/review-fix-loop
```

然后开启一个新的 Codex 会话，在目标仓库里说：

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

### 常用用法

跑一轮 review/fix：

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

最多跑 3 轮：

```text
Use $review-fix-loop with max round 3.
```

只检查某个工作流：

```text
Use $review-fix-loop with max round 3. Review only the local one-click install/run path.
```

如果你要创建定时自动化，需要明确说 cadence。`max round 3` 只是上限，不代表“每小时跑一次”：

```text
Use $review-fix-loop with max round 3, hourly.
```

### Runner 模式

这个仓库自带命令行 runner，适合直接从终端启动多个子 Codex 会话。

轻量 batch 模式：一次 review 找最多 N 个 P0/P1 问题，再用一次 fix 修复安全、连贯的一批问题。

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode batch \
  --test-profile focused \
  --review-prompt "review only the local one-click install/run path"
```

严格 paired 模式：每一轮都是一个独立 review 子会话，必要时再开一个独立 fix 子会话。

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode paired \
  --review-prompt "review repo，看是否能满足大部分用户的本地一键使用"
```

常用参数：

- `--runner-mode batch`: 更轻量，适合本地快速检查多个问题。
- `--runner-mode paired`: 更可追踪，适合严格逐轮审查。
- `--test-profile focused`: 默认，只跑和改动相关的便宜测试。
- `--test-profile final-full`: 中间轮跑 focused，最后一轮跑更完整验证。
- `--test-profile full`: 每次修复后都尽量跑完整验证。
- `--state-dir tmp`: 把状态放到 tmp，目标仓库不需要 `.codex`。
- `--prompt-profile skill`: 调试 skill 本身时才需要，让子会话加载完整 skill。
- `--ignore-user-config`: 当用户级配置或插件同步造成噪声时使用。

macOS 上 runner 会优先使用 `/Applications/Codex.app/Contents/Resources/codex`，避免 npm wrapper 在 tmp 状态目录下解析不一致。可以用 `CODEX_BIN` 或 `--codex-bin` 覆盖。

### 配置

`max_loop` 是最多跑几轮，不是定时频率。配置优先级：

1. 当前用户请求。
2. 仓库配置：`.codex/review-loop.config.md`。
3. 用户配置：`${CODEX_HOME:-~/.codex}/review-loop.config.md`。
4. 默认值：`10`。

配置文件使用简单的 `key: value`：

```yaml
max_loop: 10
state_dir: tmp
continuous_mode: pair-sessions
session_runner: codex-exec
automation_cadence: require-explicit
```

`state_dir` 支持：

- `auto`: 如果仓库里已有可写 `.codex` 就用它，否则用 tmp。
- `repo`: 使用仓库 `.codex`，需要时创建。
- `tmp`: 使用 `${TMPDIR:-/tmp}/codex-review-loop/<repo-id>`。
- 绝对路径：使用指定目录。

### 自定义 review/fix 提示

可以在解析后的状态目录或仓库 `.codex/` 下创建 `review-loop.prompts.md`：

```markdown
# Review Prompt

Review only the payment and auth paths. Keep the P0/P1 severity gate, and prioritize permission bypass, account isolation, and data-loss bugs.

# Fix Prompt

Fix the selected issue with the smallest patch possible. Prefer existing helpers and add a focused regression test before broadening the suite.
```

缺少某个 section 时会回退到默认提示。当前用户在聊天里的明确要求优先级最高。

## English

### What It Is

`codex-review-loop` is a Codex skill for repeatable repository review/fix passes. It keeps the loop focused on severe, actionable issues instead of turning a review into a general backlog.

By default it:

- reviews only for real P0/P1 correctness, security, data integrity, and core workflow failures;
- keeps review sessions read-only;
- fixes only the selected issue or selected safe batch;
- adds or updates regression coverage;
- commits fixes after tests pass;
- records durable loop state in `review-loop.md`.

### When To Use It

Use it when you want Codex to:

- check a release-critical workflow before shipping;
- verify a local install/run path;
- look for serious regressions after a large change;
- run several review/fix rounds without keeping the current chat in an open-ended loop.

Do not use it as a replacement for CI, broad style review, or P2/P3 backlog generation.

### Install

Clone this repository into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:7oru/codex-review-loop.git ~/.codex/skills/review-fix-loop
```

Start a new Codex session in your target repository and ask:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

### Common Usage

Run one pass:

```text
Use $review-fix-loop to run one review/fix loop in this repository.
```

Run up to three rounds:

```text
Use $review-fix-loop with max round 3.
```

Limit the review scope:

```text
Use $review-fix-loop with max round 3. Review only the local one-click install/run path.
```

If you want a scheduled automation, say the cadence explicitly. `max round 3` is only a cap:

```text
Use $review-fix-loop with max round 3, hourly.
```

### Runner Modes

The bundled runner starts child `codex exec` sessions for you.

Batch mode is lighter: one review session can report up to N P0/P1 findings, then one fix session repairs the safe coherent batch.

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode batch \
  --test-profile focused \
  --review-prompt "review only the local one-click install/run path"
```

Paired mode is stricter: each round starts a fresh review session and, when needed, a fresh fix session.

```bash
python3 ~/.codex/skills/review-fix-loop/scripts/run_codex_pair_loop.py \
  --repo /path/to/repo \
  --max-rounds 3 \
  --runner-mode paired \
  --review-prompt "review whether most users can run this locally in one command"
```

Useful options:

- `--runner-mode batch`: faster local multi-finding review/fix.
- `--runner-mode paired`: stricter per-round traceability.
- `--test-profile focused`: run cheap tests for touched behavior.
- `--test-profile final-full`: run focused tests during the loop and broader validation at the end.
- `--test-profile full`: run the broadest practical validation after each fix.
- `--state-dir tmp`: keep loop state outside the target repository.
- `--prompt-profile skill`: load the full skill in child sessions, mainly for debugging the skill itself.
- `--ignore-user-config`: reduce noise from user-level config or plugin sync.

On macOS, the runner prefers `/Applications/Codex.app/Contents/Resources/codex` over the npm wrapper. Override it with `CODEX_BIN` or `--codex-bin` when needed.

### Configuration

`max_loop` is a round cap, not a schedule. Configuration precedence:

1. Current user request.
2. Repository config: `.codex/review-loop.config.md`.
3. User config: `${CODEX_HOME:-~/.codex}/review-loop.config.md`.
4. Default: `10`.

Config files use simple `key: value` lines:

```yaml
max_loop: 10
state_dir: tmp
continuous_mode: pair-sessions
session_runner: codex-exec
automation_cadence: require-explicit
```

Supported `state_dir` values:

- `auto`: use repo `.codex` only if it already exists and is writable; otherwise use tmp.
- `repo`: use repo `.codex` and create it if needed.
- `tmp`: use `${TMPDIR:-/tmp}/codex-review-loop/<repo-id>`.
- absolute path: use that path.

### Prompt Overrides

Create `review-loop.prompts.md` in the resolved state directory or in the repository `.codex/` directory:

```markdown
# Review Prompt

Review only the payment and auth paths. Keep the P0/P1 severity gate, and prioritize permission bypass, account isolation, and data-loss bugs.

# Fix Prompt

Fix the selected issue with the smallest patch possible. Prefer existing helpers and add a focused regression test before broadening the suite.
```

Each section is optional. Missing sections fall back to the default prompts. Current user instructions for a run take priority over the file.

## Description Guidance

For the GitHub repository description, use a short product-style sentence:

```text
Codex skill for P0/P1 repository review/fix loops with paired or batch codex exec runners.
```

For the skill frontmatter `description`, use trigger-oriented wording so Codex knows when to load it:

```text
Use when the user asks Codex to review a repository for actionable P0/P1 issues, fix the selected issue or safe batch, add regression tests, commit the fix, and record loop state. Supports single-pass, paired, batch, max-round, prompt overrides, tmp/repo state, and explicit automations.
```

## License

MIT
