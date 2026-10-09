# S6 守卫演示 brief（单页）

> 配套：`docs/ppt/s5-closed-loop-demo.md`（S5 闭环）。两者合起来就是 Step 8 要的"**一个 5 分钟 demo**"。
> 数据来源：`prototype/out/s6_summary.json`、`out/s6_threshold_sweep.json`、`out/s6/guards_*.jsonl`。全部离线、确定性、秒级。

## 1. 一句话

**给闭环装上"自我纠错"：主题漂移 / 死循环 / 停滞 / 预算超限都能被检出，并按"重试 → 降级 → 回退 → 终止"的阶梯处置，全程留事件可读作"起因 → 检出 → 处置 → 结果"。**

## 2. 四个守卫（本轮落地）

| 守卫 | 判据 | 动作 | 实测 |
|---|---|---|---|
| **G1 主题漂移** | 产物 vs **scope 质心** 的相似度 | warn→retry；block→**replan**（回退检索 + 注入恢复包） | 3/3 检出 |
| **G4 死循环** | 工具签名（名+参数哈希）窗口 k=5 内重复 ≥3 | 首次 **replan**；再次 **abort** | 3/3 检出 |
| **停滞** | 连续 2 步"零新增" | 首次 **degrade**（换源）；持续 **abort** | 3/3 检出 |
| **预算看门狗** | token/时长/成本/步数 4 维 | **80% warn（不阻断）→ 100% stop** | 3/3 检出 |

## 3. 关键实测数字

### 3.1 阈值标定（本步最有价值的部分）

| scope 表示 | 正样本（同主题 24 篇） | 负样本（离题 8 篇，真实 CRISPR 论文） | 是否可分 | 零误报下的表现 |
|---|---|---|---|---|
| 关键词字符串（spec 字面写法） | 0.000–0.165 | 0.000–0.029 | ❌ **重叠** | thr=0.02 → 检出 0.88 / **误报 0.29**；**没有可用阈值** |
| **种子语料质心**（本轮改用） | **0.0885–0.2149** | **0.0330–0.0670** | ✅ 可分 | **block 0.0777 / warn 0.0867 → 检出 1.0 / 误报 0.0** |

> 讲给导师的一句话：**spec 写的"关键词 scope + 绝对阈值"在实测中不可行；改成"种子语料质心"后正负样本才真正分开。**
> 另一个教训：warn 阈值**不能拍成 block×常数**——第一版取 0.12 落进了正样本分布内部，导致 3/3 正常 run 误报。

### 3.2 注入矩阵（6 场景 × 3 次，全离线）

| 场景 | 检出率 | 处置与结果 |
|---|---|---|
| 正常（不注入） | **0/3 误报** | 3/3 正常完成 ✅ |
| 漂移 | 1.00 | replan → 恢复完成 |
| 循环 | 1.00 | replan → abort（6 步内终止，不空转烧预算） |
| 停滞 | 1.00 | degrade → abort |
| provider 超时 | 1.00 | 重试 + 降级换通道 → 恢复完成 |
| 预算超限 | 1.00 | 80% warn → 100% stop |

**验收**：注入检出率 **1.00 ≥ 0.9** ✅｜正常误报 **0/3** ✅｜全部"恢复到完成态或按规则终止" ✅

### 3.3 事件链（可读作 起因→检出→处置→结果）

```json
{"type":"tool_call",     "payload":{"tool":"openalex_search","params_hash":"openalex_search:ab12…"}}
{"type":"guard_trigger", "severity":"warning","payload":{"code":"E_GUARD_LOOP","action":"replan",
                                                          "reasons":["窗口 k=5 内重复签名 3 次（阈值 3）", …]}}
{"type":"recovery",      "payload":{"action":"replan","recovery_packet":{"failure":{"stage":"step3"},
                                          "trusted_state":{"strategy":"whitelist","verified_claims":0},
                                          "next_constraints":["只使用本 run 已验证的论文", …]}}}
{"type":"metric",        "payload":{"scenario":"loop","guard_hits":2,"recovered":false,"aborted":true}}
```

## 4. 工程规则（本轮确立，写进设计文档）

1. **G1 的判据是"表示 + 阈值"两件事**：表示不对（关键词串），阈值怎么调都没用。
2. **两级阈值都按分布标定**：block = 间隙中点；warn = 正样本下界 ×(1−margin)；禁止拍常数。
3. **检索与守卫共用同一打分器**（`lit_agent_min/scoring.py`）：S5 检索已改为委托该模块，复跑仍 4/4 命中缓存、$0。
4. **恢复包是可注入的最小结构**：`guard{code,action}` + `failure{stage,attempt,reasons}` + `trusted_state` + `next_constraints`。

## 5. 诚实边界

| 未做 | 原因 |
|---|---|
| embedding 版 G1 | 无本地 bge-m3；本轮用词法质心代理，**Phase 1 换 embedding 后必须重新标定阈值** |
| G2/G3/G5–G15 全量实现 | 本轮 spec 只要求"两个守卫 + 预算看门狗 + 注入钩子" |
| 真实故障注入（真断网/真超时/真 kill） | 本轮验证的是**守卫逻辑与处置阶梯**；故障用确定性模拟注入，换真故障只需替换注入点 |
| 恢复包 A/B 有效性对比 | spec 的"失败应对"项，列入 S7/Phase 1（需要对照组样本量） |

## 6. 演示命令

```bash
cd prototype
uv run python steps/s6_guards_demo.py --sweep                      # 阈值标定（TPR/FPR 全表）
uv run python steps/s6_guards_demo.py --inject all --repeats 3     # 6 场景 × 3 次，约 3 秒
uv run python steps/s6_guards_demo.py --inject drift --repeats 3    # 只演示漂移
uv run python steps/s6_guards_demo.py --inject loop  --repeats 3    # 只演示循环（replan→abort）
```

## 7. 3 分钟讲法

1. **讲问题**（30 s）：闭环能出报告了，但它会不会"跑偏、卡死、烧钱"？——守卫就是回答这个。
2. **讲标定**（60 s）：展示 `--sweep` 输出两张分布：关键词 scope 下正负重叠（**阈值失效**）→ 换质心后完全分开（0.0885 vs 0.0670）→ 定出 0.0777/0.0867。**这是"用实测标定阈值"而不是"拍数字"的过程。**
3. **讲矩阵**（60 s）：跑 `--inject all`，指出四类注入检出率 100%、正常 run 误报 0、循环场景 6 步内就 abort（不空转）。
4. **讲设计原则**（30 s）：守卫是**纯判定 + 确定性打分的代码**，不是提示词；阈值有分布依据；事件链可复盘。
