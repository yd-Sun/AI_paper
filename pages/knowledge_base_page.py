# -*- coding: utf-8 -*-
"""
知识库管理与资料选择窗口。
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from modules.knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseStore,
    PAPER_WRITE_SCENE_IDS,
)
from modules.prompt_center import SCENE_DEFS
from modules.ui_components import (
    COLORS,
    FONTS,
    ToggleSwitch,
    create_home_shell_button,
    THEMES,
)


def _scene_label(scene_id):
    scene = SCENE_DEFS.get(scene_id, {})
    page_label = scene.get('page_label', '')
    label = scene.get('label', '')
    if page_label and label:
        return f'{page_label} · {label}'
    return label or page_label or scene_id


def _scope_summary(scene_ids):
    labels = [_scene_label(scene_id).split(' · ')[-1] for scene_id in list(scene_ids or [])]
    if not labels:
        return '未绑定'
    if len(labels) <= 2:
        return '、'.join(labels)
    return f'{"、".join(labels[:2])} 等 {len(labels)} 项'


class KnowledgeBasePanel:
    """知识库管理面板。"""

    def __init__(self, parent, store: KnowledgeBaseStore, set_status=None, close_panel=None):
        self.parent = parent
        self.store = store
        self.set_status = set_status or (lambda *_args, **_kwargs: None)
        self.close_panel = close_panel
        self.frame = tk.Frame(parent, bg=COLORS['bg_main'])
        self.projects = []
        self.documents = []
        self.current_project_id = ''
        self.current_document_id = ''
        self.scene_vars = {}
        self.title_var = tk.StringVar()
        self.tags_var = tk.StringVar()
        self.enabled_var = tk.BooleanVar(value=True)
        self._build()
        self.refresh_all()

    def _build(self):
        header = tk.Frame(self.frame, bg=COLORS['bg_main'])
        header.pack(fill=tk.X, pady=(0, 16))
        tk.Label(
            header,
            text='知识库',
            font=FONTS['title'],
            fg=COLORS['text_main'],
            bg=COLORS['bg_main'],
        ).pack(side=tk.LEFT)
        tk.Label(
            header,
            text='独立多项目资料库，论文写作请求按本次选择使用资料。',
            font=FONTS['small'],
            fg=COLORS['text_sub'],
            bg=COLORS['bg_main'],
        ).pack(side=tk.LEFT, padx=(14, 0))
        if callable(self.close_panel):
            save_shell, _button = create_home_shell_button(
                header,
                '保存资料',
                command=self._save_document,
                style='primary_fixed',
                padx=18,
                pady=8,
                border_color=THEMES['light']['card_border'],
            )
            save_shell.pack(side=tk.RIGHT)

        body = tk.Frame(self.frame, bg=COLORS['bg_main'])
        body.pack(fill=tk.BOTH, expand=True)

        left_card = tk.Frame(body, bg=COLORS['card_bg'], highlightthickness=1, highlightbackground=COLORS['card_border'])
        left_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 14))
        project_header = tk.Frame(left_card, bg=COLORS['card_bg'])
        project_header.pack(fill=tk.X, padx=14, pady=(14, 8))
        tk.Label(
            project_header,
            text='项目',
            font=FONTS['body_bold'],
            fg=COLORS['text_main'],
            bg=COLORS['card_bg'],
        ).pack(side=tk.LEFT)
        create_shell, _button = create_home_shell_button(
            project_header,
            '创建项目',
            command=self._create_project,
            style='primary_fixed',
            padx=12,
            pady=5,
            border_color=THEMES['light']['card_border'],
        )
        create_shell.pack(side=tk.RIGHT)
        list_shell = tk.Frame(left_card, bg=COLORS['input_bg'], highlightthickness=1, highlightbackground=COLORS['card_border'])
        list_shell.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))
        self.project_list = tk.Listbox(
            list_shell,
            width=28,
            activestyle='none',
            bd=0,
            highlightthickness=0,
            bg=COLORS['input_bg'],
            fg=COLORS['text_main'],
            selectbackground=COLORS['primary'],
            selectforeground='#FFFFFF',
            font=FONTS['body'],
        )
        self.project_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        project_scroll = ttk.Scrollbar(list_shell, orient=tk.VERTICAL, command=self.project_list.yview)
        project_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.project_list.configure(yscrollcommand=project_scroll.set)
        self.project_list.bind('<<ListboxSelect>>', lambda _event: self._on_project_selected())
        project_actions = tk.Frame(left_card, bg=COLORS['card_bg'])
        project_actions.pack(fill=tk.X, padx=14, pady=(0, 14))
        for label, command in (
            ('重命名', self._rename_project),
            ('删除', self._delete_project),
        ):
            shell, _button = create_home_shell_button(
                project_actions,
                label,
                command=command,
                style='secondary',
                padx=12,
                pady=7,
            )
            shell.pack(side=tk.LEFT, padx=(0, 8))

        right = tk.Frame(body, bg=COLORS['bg_main'])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        docs_card = tk.Frame(right, bg=COLORS['card_bg'], highlightthickness=1, highlightbackground=COLORS['card_border'])
        docs_card.pack(fill=tk.BOTH, expand=True)
        docs_header = tk.Frame(docs_card, bg=COLORS['card_bg'])
        docs_header.pack(fill=tk.X, padx=14, pady=(14, 8))
        tk.Label(
            docs_header,
            text='资料',
            font=FONTS['body_bold'],
            fg=COLORS['text_main'],
            bg=COLORS['card_bg'],
        ).pack(side=tk.LEFT)
        for label, command, style in (
            ('导入资料', self._import_documents, 'primary_fixed'),
            ('删除资料', self._delete_document, 'secondary'),
        ):
            shell, _button = create_home_shell_button(
                docs_header,
                label,
                command=command,
                style=style,
                padx=14,
                pady=7,
                border_color=THEMES['light']['card_border'] if style == 'primary_fixed' else None,
            )
            shell.pack(side=tk.RIGHT, padx=(8, 0))

        columns = ('title', 'type', 'chars', 'enabled', 'scope')
        self.docs_tree = ttk.Treeview(docs_card, columns=columns, show='headings', height=9)
        for col, title, width in (
            ('title', '标题', 320),
            ('type', '类型', 70),
            ('chars', '字符数', 80),
            ('enabled', '状态', 70),
            ('scope', '范围：', 260),
        ):
            self.docs_tree.heading(col, text=title)
            self.docs_tree.column(col, width=width, anchor='w')
        self.docs_tree.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 12))
        self.docs_tree.bind('<<TreeviewSelect>>', lambda _event: self._on_document_selected())

        detail = tk.Frame(docs_card, bg=COLORS['surface_alt'], highlightthickness=1, highlightbackground=COLORS['card_border'])
        detail.pack(fill=tk.X, padx=14, pady=(0, 14))
        form = tk.Frame(detail, bg=COLORS['surface_alt'])
        form.pack(fill=tk.X, padx=12, pady=12)
        tk.Label(form, text='标题', font=FONTS['small'], fg=COLORS['text_sub'], bg=COLORS['surface_alt']).grid(row=0, column=0, sticky='w')
        title_entry = tk.Entry(form, textvariable=self.title_var, font=FONTS['body'], bg=COLORS['input_bg'], fg=COLORS['text_main'], relief=tk.FLAT)
        title_entry.grid(row=0, column=1, sticky='ew', padx=(8, 12), ipady=4)
        tk.Label(form, text='标签', font=FONTS['small'], fg=COLORS['text_sub'], bg=COLORS['surface_alt']).grid(row=0, column=2, sticky='w')
        tags_entry = tk.Entry(form, textvariable=self.tags_var, font=FONTS['body'], bg=COLORS['input_bg'], fg=COLORS['text_main'], relief=tk.FLAT)
        tags_entry.grid(row=0, column=3, sticky='ew', padx=(8, 0), ipady=4)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        check_row = tk.Frame(detail, bg=COLORS['surface_alt'])
        check_row.pack(fill=tk.X, padx=12, pady=(0, 10))
        enabled_row = tk.Frame(check_row, bg=COLORS['surface_alt'])
        enabled_row.pack(side=tk.LEFT)
        tk.Label(enabled_row, text='启用', font=FONTS['body'], fg=COLORS['text_main'], bg=COLORS['surface_alt']).pack(side=tk.LEFT)
        ToggleSwitch(enabled_row, variable=self.enabled_var, bg=COLORS['surface_alt']).pack(side=tk.LEFT, padx=(6, 0))
        tk.Label(check_row, text='范围：', font=FONTS['body'], fg=COLORS['text_main'], bg=COLORS['surface_alt']).pack(side=tk.LEFT, padx=(18, 6))
        self.scope_frame = tk.Frame(check_row, bg=COLORS['surface_alt'])
        self.scope_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for scene_id in PAPER_WRITE_SCENE_IDS:
            var = tk.BooleanVar(value=True)
            self.scene_vars[scene_id] = var
            scene_row = tk.Frame(self.scope_frame, bg=COLORS['surface_alt'])
            scene_row.pack(side=tk.LEFT, padx=(0, 12))
            tk.Label(scene_row, text=_scene_label(scene_id).split(' · ')[-1], font=FONTS['small'], fg=COLORS['text_main'], bg=COLORS['surface_alt']).pack(side=tk.LEFT)
            ToggleSwitch(scene_row, variable=var, width=36, height=20, bg=COLORS['surface_alt']).pack(side=tk.LEFT, padx=(4, 0))

        tk.Label(
            detail,
            text='文本预览',
            font=FONTS['small'],
            fg=COLORS['text_sub'],
            bg=COLORS['surface_alt'],
        ).pack(anchor='w', padx=12)
        self.preview_text = tk.Text(
            detail,
            height=7,
            wrap=tk.WORD,
            bg=COLORS['input_bg'],
            fg=COLORS['text_main'],
            relief=tk.FLAT,
            font=FONTS['small'],
        )
        self.preview_text.pack(fill=tk.X, padx=12, pady=(6, 12))
        self.preview_text.configure(state='disabled')

    def refresh_all(self, preferred_project_id='', preferred_document_id=''):
        self._refresh_projects(preferred_project_id or self.current_project_id)
        if not self.current_project_id and self.projects:
            self.current_project_id = self.projects[0]['id']
        self._select_project_in_list(self.current_project_id)
        self._refresh_documents(preferred_document_id or self.current_document_id)

    def _refresh_projects(self, preferred_project_id=''):
        self.projects = self.store.list_projects()
        self.project_list.delete(0, tk.END)
        for project in self.projects:
            self.project_list.insert(tk.END, project['name'])
        ids = {project['id'] for project in self.projects}
        if preferred_project_id in ids:
            self.current_project_id = preferred_project_id
        elif self.projects:
            self.current_project_id = self.projects[0]['id']
        else:
            self.current_project_id = ''

    def _select_project_in_list(self, project_id):
        self.project_list.selection_clear(0, tk.END)
        for index, project in enumerate(self.projects):
            if project['id'] == project_id:
                self.project_list.selection_set(index)
                self.project_list.activate(index)
                break

    def _refresh_documents(self, preferred_document_id=''):
        for item in self.docs_tree.get_children():
            self.docs_tree.delete(item)
        self.documents = self.store.list_documents(self.current_project_id) if self.current_project_id else []
        ids = {document['id'] for document in self.documents}
        self.current_document_id = preferred_document_id if preferred_document_id in ids else ''
        for document in self.documents:
            self.docs_tree.insert(
                '',
                tk.END,
                iid=document['id'],
                values=(
                    document.get('title', ''),
                    document.get('source_type', ''),
                    document.get('char_count', 0),
                    '启用' if document.get('enabled', True) else '停用',
                    _scope_summary(document.get('bound_scene_ids', [])),
                ),
            )
        if self.current_document_id:
            self.docs_tree.selection_set(self.current_document_id)
            self.docs_tree.focus(self.current_document_id)
        elif self.documents:
            self.current_document_id = self.documents[0]['id']
            self.docs_tree.selection_set(self.current_document_id)
            self.docs_tree.focus(self.current_document_id)
        self._load_document_detail()

    def _on_project_selected(self):
        selection = self.project_list.curselection()
        if not selection:
            return
        index = selection[0]
        if 0 <= index < len(self.projects):
            self.current_project_id = self.projects[index]['id']
            self.current_document_id = ''
            self._refresh_documents()

    def _on_document_selected(self):
        selection = self.docs_tree.selection()
        self.current_document_id = selection[0] if selection else ''
        self._load_document_detail()

    def _load_document_detail(self):
        document = self.store.get_document(self.current_document_id) if self.current_document_id else None
        self.title_var.set(document.get('title', '') if document else '')
        self.tags_var.set('，'.join(document.get('tags', [])) if document else '')
        self.enabled_var.set(bool(document.get('enabled', True)) if document else True)
        bound = set(document.get('bound_scene_ids', PAPER_WRITE_SCENE_IDS) if document else PAPER_WRITE_SCENE_IDS)
        for scene_id, var in self.scene_vars.items():
            var.set(scene_id in bound)
        preview = self.store.read_document_text(document) if document else ''
        self.preview_text.configure(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.insert('1.0', preview[:6000])
        self.preview_text.configure(state='disabled')

    def _create_project(self):
        name = simpledialog.askstring('新建知识库项目', '请输入项目名称：', parent=self.frame)
        if not name:
            return
        try:
            project = self.store.create_project(name)
        except Exception as exc:
            messagebox.showerror('知识库', str(exc), parent=self.frame)
            return
        self.set_status('知识库项目已创建', COLORS['success'])
        self.refresh_all(preferred_project_id=project['id'])

    def _rename_project(self):
        project = self.store.get_project(self.current_project_id)
        if not project:
            messagebox.showwarning('知识库', '请先选择项目。', parent=self.frame)
            return
        name = simpledialog.askstring('重命名知识库项目', '请输入新的项目名称：', initialvalue=project['name'], parent=self.frame)
        if not name:
            return
        try:
            self.store.update_project(project['id'], name=name)
        except Exception as exc:
            messagebox.showerror('知识库', str(exc), parent=self.frame)
            return
        self.set_status('知识库项目已重命名', COLORS['success'])
        self.refresh_all(preferred_project_id=project['id'])

    def _delete_project(self):
        project = self.store.get_project(self.current_project_id)
        if not project:
            messagebox.showwarning('知识库', '请先选择项目。', parent=self.frame)
            return
        if not messagebox.askyesno('删除知识库项目', f'确定删除“{project["name"]}”及其全部资料吗？', parent=self.frame):
            return
        try:
            self.store.delete_project(project['id'])
        except Exception as exc:
            messagebox.showerror('知识库', str(exc), parent=self.frame)
            return
        self.set_status('知识库项目已删除', COLORS['success'])
        self.refresh_all()

    def _import_documents(self):
        if not self.current_project_id:
            messagebox.showwarning('知识库', '请先创建或选择项目。', parent=self.frame)
            return
        paths = filedialog.askopenfilenames(
            title='导入知识库资料',
            filetypes=[
                ('支持的资料文件', '*.txt *.md *.docx *.pdf'),
                ('文本文件', '*.txt *.md'),
                ('Word 文档', '*.docx'),
                ('PDF 文件', '*.pdf'),
            ],
            parent=self.frame,
        )
        if not paths:
            return
        imported = []
        failed = []
        for path in paths:
            try:
                imported.append(self.store.import_document(self.current_project_id, path))
            except Exception as exc:
                failed.append(f'{os.path.basename(path)}：{exc}')
        if failed:
            messagebox.showwarning('知识库导入', '\n'.join(failed), parent=self.frame)
        if imported:
            self.set_status(f'已导入 {len(imported)} 份知识库资料', COLORS['success'])
            self.refresh_all(preferred_document_id=imported[-1]['id'])

    def _save_document(self):
        if not self.current_document_id:
            messagebox.showwarning('知识库', '请先选择资料。', parent=self.frame)
            return
        scene_ids = [scene_id for scene_id, var in self.scene_vars.items() if var.get()]
        try:
            document = self.store.update_document(
                self.current_document_id,
                title=self.title_var.get(),
                tags=self.tags_var.get(),
                enabled=self.enabled_var.get(),
                bound_scene_ids=scene_ids,
            )
        except Exception as exc:
            messagebox.showerror('知识库', str(exc), parent=self.frame)
            return
        self.set_status('知识库资料设置已保存', COLORS['success'])
        self.refresh_all(preferred_project_id=document['project_id'], preferred_document_id=document['id'])
        if callable(self.close_panel):
            self.close_panel()

    def _delete_document(self):
        document = self.store.get_document(self.current_document_id)
        if not document:
            messagebox.showwarning('知识库', '请先选择资料。', parent=self.frame)
            return
        if not messagebox.askyesno('删除知识库资料', f'确定删除“{document["title"]}”吗？', parent=self.frame):
            return
        try:
            self.store.delete_document(document['id'])
        except Exception as exc:
            messagebox.showerror('知识库', str(exc), parent=self.frame)
            return
        self.set_status('知识库资料已删除', COLORS['success'])
        self.refresh_all(preferred_project_id=document['project_id'])


class KnowledgeContextDialog:
    """论文写作请求前的本次资料选择弹窗。"""

    def __init__(self, parent, store: KnowledgeBaseStore, scene_id, action_label='',
                 total_char_limit=None, per_document_char_limit=None):
        from modules.knowledge_base import DEFAULT_TOTAL_CHAR_LIMIT, DEFAULT_PER_DOCUMENT_CHAR_LIMIT
        self.parent = parent
        self.store = store
        self.scene_id = str(scene_id or '').strip()
        self.action_label = str(action_label or '').strip()
        self.total_char_limit = total_char_limit or DEFAULT_TOTAL_CHAR_LIMIT
        self.per_document_char_limit = per_document_char_limit or DEFAULT_PER_DOCUMENT_CHAR_LIMIT
        self.result = None
        self.projects = []
        self.current_project_id = ''
        self.documents = []
        self.document_ids_by_index = []
        self.document_selected = []
        self.window = None
        self.project_var = tk.StringVar()

    def show(self):
        self.window = tk.Toplevel(self.parent)
        self.window.title('选择知识库资料')
        self.window.configure(bg=COLORS['bg_main'])
        self.window.transient(self.parent)
        self.window.geometry('1600x1200')
        self.window.minsize(1360, 960)
        self.window.grab_set()
        self.window.protocol('WM_DELETE_WINDOW', self._cancel)
        self._build()
        self._refresh_projects()
        self.window.wait_window()
        return self.result

    def _build(self):
        container = tk.Frame(self.window, bg=COLORS['bg_main'])
        container.pack(fill=tk.BOTH, expand=True, padx=22, pady=22)
        title = '选择知识库资料'
        if self.action_label:
            title = f'{title}：{self.action_label}'
        tk.Label(
            container,
            text=title,
            font=FONTS['title'],
            fg=COLORS['text_main'],
            bg=COLORS['bg_main'],
        ).pack(anchor='w')
        tk.Label(
            container,
            text=f'当前场景：{_scene_label(self.scene_id)}。取消会中止本次生成，跳过知识库会继续正常生成。',
            font=FONTS['small'],
            fg=COLORS['text_sub'],
            bg=COLORS['bg_main'],
        ).pack(anchor='w', pady=(6, 4))
        tk.Label(
            container,
            text=f'当前模型预算：总计 {self.total_char_limit} 字，单份 {self.per_document_char_limit} 字',
            font=FONTS['small'],
            fg=COLORS['text_sub'],
            bg=COLORS['bg_main'],
        ).pack(anchor='w', pady=(0, 12))

        project_row = tk.Frame(container, bg=COLORS['bg_main'])
        project_row.pack(fill=tk.X, pady=(0, 12))
        tk.Label(project_row, text='项目', font=FONTS['body_bold'], fg=COLORS['text_main'], bg=COLORS['bg_main']).pack(side=tk.LEFT)
        self.project_combo = ttk.Combobox(project_row, textvariable=self.project_var, state='readonly', width=42)
        self.project_combo.pack(side=tk.LEFT, padx=(10, 0))
        self.project_combo.bind('<<ComboboxSelected>>', lambda _event: self._on_project_changed())

        footer = tk.Frame(container, bg=COLORS['bg_main'])
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(16, 0))
        for label, command, style in (
            ('取消', self._cancel, 'secondary'),
            ('跳过知识库', self._skip, 'secondary'),
            ('使用所选资料', self._use_selected, 'primary_fixed'),
        ):
            shell, _button = create_home_shell_button(
                footer,
                label,
                command=command,
                style=style,
                padx=28,
                pady=12,
                border_color=THEMES['light']['card_border'] if style == 'primary_fixed' else None,
            )
            shell.pack(side=tk.RIGHT, padx=(10, 0))

        list_shell = tk.Frame(container, bg=COLORS['card_bg'], highlightbackground=COLORS['card_border'], highlightthickness=1)
        list_shell.pack(fill=tk.BOTH, expand=True)
        columns = ('check', 'title', 'chars', 'tags')
        self.docs_tree = ttk.Treeview(list_shell, columns=columns, show='headings', selectmode='none', height=16)
        for col, title, width, anchor in (
            ('check', '', 50, 'center'),
            ('title', '标题', 420, 'w'),
            ('chars', '字符数', 100, 'w'),
            ('tags', '标签', 200, 'w'),
        ):
            self.docs_tree.heading(col, text=title)
            self.docs_tree.column(col, width=width, anchor=anchor, stretch=True if col == 'title' else False)
        self.docs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=12)
        scroll = ttk.Scrollbar(list_shell, orient=tk.VERTICAL, command=self.docs_tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 12), pady=12)
        self.docs_tree.configure(yscrollcommand=scroll.set)
        self.docs_tree.bind('<Button-1>', self._on_tree_click)

    def _refresh_projects(self):
        self.projects = self.store.list_projects()
        names = [project['name'] for project in self.projects]
        self.project_combo.configure(values=names)
        if self.projects:
            self.current_project_id = self.projects[0]['id']
            self.project_var.set(self.projects[0]['name'])
        else:
            self.current_project_id = ''
            self.project_var.set('')
        self._refresh_documents()

    def _on_project_changed(self):
        index = self.project_combo.current()
        if 0 <= index < len(self.projects):
            self.current_project_id = self.projects[index]['id']
        else:
            self.current_project_id = ''
        self._refresh_documents()

    def _refresh_documents(self):
        for item in self.docs_tree.get_children():
            self.docs_tree.delete(item)
        self.document_ids_by_index = []
        self.document_selected = []
        if not self.current_project_id:
            self.docs_tree.insert('', tk.END, values=('', '暂无知识库项目。', '', ''))
            return
        self.documents = self.store.list_documents(
            self.current_project_id,
            scene_id=self.scene_id,
            enabled_only=True,
        )
        if not self.documents:
            self.docs_tree.insert('', tk.END, values=('', '当前项目没有可用于该场景的启用资料。', '', ''))
            return
        for index, document in enumerate(self.documents):
            tags = document.get('tags', [])
            tag_text = '、'.join(tags) if tags else ''
            self.document_ids_by_index.append(document['id'])
            self.document_selected.append(False)
            iid = f'doc_{index}'
            self.docs_tree.insert('', tk.END, iid=iid, values=(
                '☐',
                document.get('title', ''),
                f'{document.get("char_count", 0)} 字',
                tag_text,
            ))

    def _on_tree_click(self, event):
        region = self.docs_tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        column = self.docs_tree.identify_column(event.x)
        if column != '#1':
            return
        iid = self.docs_tree.identify_row(event.y)
        if not iid or not iid.startswith('doc_'):
            return
        index = int(iid.split('_', 1)[1])
        if index < 0 or index >= len(self.document_selected):
            return
        self.document_selected[index] = not self.document_selected[index]
        checked = '☑' if self.document_selected[index] else '☐'
        self.docs_tree.item(iid, values=(checked, *self.docs_tree.item(iid, 'values')[1:]))

    def _use_selected(self):
        selected_ids = [
            self.document_ids_by_index[index]
            for index, selected in enumerate(self.document_selected)
            if selected and 0 <= index < len(self.document_ids_by_index)
        ]
        if not selected_ids:
            messagebox.showwarning('知识库', '请选择至少一份资料，或点击“跳过知识库”。', parent=self.window)
            return
        context = self.store.build_context(
            self.current_project_id, selected_ids, self.scene_id,
            total_char_limit=self.total_char_limit,
            per_document_char_limit=self.per_document_char_limit,
        )
        if not context.get('context_text'):
            messagebox.showwarning('知识库', '所选资料没有可用文本。', parent=self.window)
            return
        self.result = context
        self.window.destroy()

    def _skip(self):
        self.result = {}
        self.window.destroy()

    def _cancel(self):
        self.result = None
        self.window.destroy()
