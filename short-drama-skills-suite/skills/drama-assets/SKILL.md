---
name: drama-assets
description: 为短剧建立角色、场景、服装和声音一致性资产计划，制作可供方舟参考图模式使用的逐镜素材清单。
---

# 短剧资产与一致性

支持将已授权参考音频/视频接入视频生成请求。清单role分别为reference_audio/reference_video，附duration_seconds；音频另需voice_consent_confirmed=true。核验实际模型后设置assets.multimodal_references_supported；只传音频还需audio_only_reference_supported。各类数量和总秒数上限必须按当前所选模型配置；默认每类3个、总15秒的保守配置不是所有模型承诺。音视频参考不能混入first_frame/last_frame模式。脚本只校验申报时长与权限标记，需自行ffprobe核实真实素材；没有自动音色克隆或绝对声线保证。

与同级global-short-drama配合。先用scripts/assets.py读取bible.json和各集script.json，输出角色设定、参考图提示词、场景清单和逐镜资产分配。文本计划不是已生成图片。生成图片时用宿主已授权图片能力或用户提供的原创/授权素材，先核验人物、服装与场景，再由用户允许的托管方式取得方舟可访问的HTTPS地址；上传前按用户约定确认。

```text
python <skill>/scripts/assets.py --bible <run>/bible.json --run <run> --out <asset-plan-directory>
```

asset-manifest.json默认没有参考图，不擅自填写权利确认。将通过审阅的素材写入shots键：格式为集号/语言/镜头编号，例如1/zh-CN/1；每项url、role、rights_confirmed、contains_real_face。角色参考统一使用reference_image；首帧或首尾帧路线使用first_frame/last_frame，不能混用。配置project.assets.manifest_path为清单绝对路径，并在确认模型支持后设置reference_images_supported=true。模型与图片上限、画幅参数按当前官方文档核验，不能通过删除水印或修改标记规避模型的人脸限制。

清单与配置参与运行哈希，生产开始后不能随意换图继续用旧镜头；需新的run。HTTPS链接失效会影响续跑，托管生命周期至少覆盖生产。密钥不写入清单。角色/音色提示和参考图能提供更完整输入，但不保证绝对锁脸、同音色或唇形同步。配音不稳定时提供已授权逐镜WAV，交drama-postproduction与生产脚本实测时长；当前本技能未内置独立TTS/克隆音色API。

官方依据：https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh 。本次已实现参考图载荷接入，真实模型效果仍需样片验收。
