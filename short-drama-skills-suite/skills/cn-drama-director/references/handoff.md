# 双技能交接协议 v2

director-brief.json是导演技能与生产技能之间的创作交接源；模型账户、预算与发布目标在project.json。配置brief_path指向它；运行状态绑定配置、导演指令与框架哈希。修改它们需新建run，防止旧镜头混进新剧。旧v1导演指令可读取，但质量模式的新剧本/圣经必须用v2；不得把旧稿直接标为审稿通过。

```json
{
  "schema_version": 2,
  "topic": "原创话题",
  "episodes": 1,
  "minutes_per_episode": 1,
  "language": "zh-CN",
  "genre": {"primary": "suspense", "secondary": ["family"], "tropes": []},
  "audience": "明确的观看人群与情境",
  "emotional_promise": "具体可兑现的情绪承诺",
  "constraints": ["原创人物与情节", "普通话配音", "外形与音色固定"],
  "episode_beats": [
    {"episode": 1, "goal": "核查一份矛盾记录", "obstacle": "家人的叙述与现场线索不同", "strategy": "查找记录对应的旧物", "choice": "把发现带回家当面核对", "consequence": "发现误解来源", "payoff": "证据解释异常，关系得到有限修复", "change": "从猜疑转向理解并承担责任", "hook": "真相兑现后的情感余韵"}
  ],
  "evidence": [{"source": "样本URL", "level": "B", "observation": "实际可核验观察", "inference": "待验证推断"}],
  "production_notes": {"visual_style": "原创动画", "voice": "标准普通话", "continuity": "固定人物ID", "pilot_first": true}
}
```

例子是1集的完整指令结构。多集episode_beats必须覆盖1..episodes全部集，v2每集至少包含goal,obstacle,strategy,choice,consequence,payoff,change,hook。genre代码来自生产技能assets/genre-frameworks.json；project.genre可设auto采用此选择，或显式填写同一选择。话题、集数、分钟数和源语言必须一致。brief_path不存在则报错，不能静默忽略导演指令。

生产输出bible.json中characters含唯一id,name,appearance,costume,voice,motivation；episode_arcs覆盖每集且包含因果任务；clues为空数组或每项id,meaning,introduced_episode,resolved_episode。分镜script.json包含schema_version=2、title、synopsis、story（七步任务）、clues（id/action/shot_id）、shots。每镜含固定时长、人物ID、scene_id、purpose、audio_kind、speaker、visual和dialogue；无台词镜头用ambience/none/空字符串。

review.json保留真实镜头证据、十维分数、类型检查、问题和输入哈希。自动返修由生产脚本执行且受次数与调用预算约束；模型审稿通过并不代表真实观众认可。规划可用宿主模型，生产内容与审稿调用方舟，不要求两个不同模型账户。
