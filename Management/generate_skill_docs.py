# -*- coding: utf-8 -*-
"""
批量为所有技能生成 SKILL.md 文档
"""

import json
import os
from pathlib import Path


def generate_skill_md(skill_json_path):
    """根据 skill.json 生成 SKILL.md"""
    with open(skill_json_path, 'r', encoding='utf-8') as f:
        skill_data = json.load(f)

    skill_id = skill_data.get('id', '')
    name = skill_data.get('name', skill_id)
    version = skill_data.get('version', 'v1.0.0')
    description = skill_data.get('description', '暂无描述')
    min_app_version = skill_data.get('min_app_version', 'v1.4.0')
    publisher = skill_data.get('publisher', 'PaperLab')
    scene_bindings = skill_data.get('scene_bindings', [])
    actions = skill_data.get('actions', [])
    global_hook = skill_data.get('global_hook', False)

    # 场景映射
    scene_map = {
        'paper_write.outline': '论文大纲生成',
        'paper_write.section': '论文章节写作',
        'paper_write.abstract': '论文摘要写作',
        'paper_write.reference': '参考文献管理',
        'paper_write.polish': '论文润色',
        'paper_write.review': '论文审阅',
    }

    # 生成 Markdown 内容
    md_content = f"""# {name}

## 基本信息

- **ID**: `{skill_id}`
- **版本**: {version}
- **最低应用版本**: {min_app_version}
- **发布者**: {publisher}

## 功能描述

{description}

## 适用场景

"""

    if global_hook:
        md_content += "- 全局生效（所有场景）\n"
    elif scene_bindings:
        for scene in scene_bindings:
            scene_name = scene_map.get(scene, scene)
            md_content += f"- {scene_name} (`{scene}`)\n"
    else:
        md_content += "- 无特定场景限制\n"

    # 功能列表
    if actions:
        md_content += "\n## 功能列表\n\n"
        for idx, action in enumerate(actions, 1):
            action_label = action.get('label', '未命名功能')
            action_desc = action.get('description', '')
            md_content += f"### {idx}. {action_label}\n\n"
            if action_desc:
                md_content += f"{action_desc}\n\n"

            # 输入参数
            input_schema = action.get('input_schema', {})
            fields = input_schema.get('fields', [])
            if fields:
                md_content += "**输入参数：**\n"
                for field in fields:
                    field_label = field.get('label', '')
                    field_required = '必填' if field.get('required', False) else '可选'
                    field_placeholder = field.get('placeholder', '')
                    field_type = field.get('type', 'text')

                    md_content += f"- **{field_label}** ({field_required})"

                    # 如果是选择框，列出选项
                    if field_type == 'select' and 'options' in field:
                        options = field.get('options', [])
                        option_labels = [opt.get('label', '') for opt in options]
                        md_content += f": {', '.join(option_labels)}"
                    elif field_placeholder:
                        md_content += f": {field_placeholder}"

                    md_content += "\n"
                md_content += "\n"

    # 使用方法
    md_content += """## 使用方法

1. 在技能中心启用该技能
2. 在对应的写作场景中，该技能会自动生效
3. 也可以在技能管理中心手动执行上述功能

## 注意事项

- 该技能需要联网才能正常工作
- 请确保应用版本满足最低版本要求
- 使用前请仔细阅读功能说明

## 更新日志

### {version} (2026-05-21)
- 初始版本发布
"""

    return md_content


def main():
    """批量生成所有技能的 SKILL.md"""
    skills_src_dir = Path(__file__).parent / 'skills_src'

    if not skills_src_dir.exists():
        print(f"错误：找不到目录 {skills_src_dir}")
        return

    generated_count = 0
    skipped_count = 0

    for skill_dir in skills_src_dir.iterdir():
        if not skill_dir.is_dir():
            continue

        skill_json_path = skill_dir / 'skill.json'
        skill_md_path = skill_dir / 'SKILL.md'

        if not skill_json_path.exists():
            print(f"跳过 {skill_dir.name}: 找不到 skill.json")
            skipped_count += 1
            continue

        try:
            md_content = generate_skill_md(skill_json_path)

            with open(skill_md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)

            print(f"✓ 已生成: {skill_dir.name}/SKILL.md")
            generated_count += 1
        except Exception as e:
            print(f"✗ 生成失败 {skill_dir.name}: {e}")
            skipped_count += 1

    print(f"\n完成！成功生成 {generated_count} 个文档，跳过 {skipped_count} 个。")


if __name__ == '__main__':
    main()
