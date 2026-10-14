# 混合账号计划字段
id：批次英文标识。
products：id、name、brief（工作区事实文件）、regulated_health（实际产品是否健康医疗类）。
accounts：id、instance_id（台账中真实实例）、platform、format（image/video/article/text）、categories、product_ids、persona、max_items、visibility。
topics：id、product_id、category、angle、framework（已拆解结构）。
先匹配产品，再按分类过滤，每个账号最多max_items条。账号ID、选题ID不可重复。输出独立job，包含产品资料指纹与输出目录。每账号不同表达，既不伪造经历也不把计划说成成片。
宿主原生模型可以按job直接创作文件；API批量生成器需明确provider/base_url/model/api_key_env配置，密钥不放JSON。先展示一条样稿，经用户风格确认再扩大生成。
