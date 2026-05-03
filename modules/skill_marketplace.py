# -*- coding: utf-8 -*-
"""
skill.sh 第三方技能市场 API 客户端。
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
import urllib.error

from modules.remote_content import normalize_version


SKILLSH_API_URL = 'https://skill.sh/api/skills.json'
CACHE_FILE_NAME = 'marketplace_cache.json'
CACHE_TTL = 300  # 5 分钟
FETCH_TIMEOUT = 15


class SkillMarketplaceClient:
    """skill.sh 第三方技能市场客户端，支持异步拉取、缓存和格式转换。"""

    def __init__(self, skills_root, scheduler, log_callback=None):
        self._skills_root = skills_root
        self._scheduler = scheduler
        self._log = log_callback
        self._cache = None
        self._cache_ts = 0
        self._lock = threading.Lock()

    def _write_log(self, msg, level='INFO'):
        if callable(self._log):
            try:
                self._log(msg, level=level)
            except Exception:
                pass

    def fetch_index(self, on_success, on_error=None, force=False):
        """异步拉取 skill.sh 技能索引，通过回调返回结果到 UI 线程。"""
        if not force:
            with self._lock:
                if self._cache and (time.time() - self._cache_ts) < CACHE_TTL:
                    self._scheduler.after(0, lambda: on_success(self._cache))
                    return

        t = threading.Thread(
            target=self._worker,
            args=(SKILLSH_API_URL, on_success, on_error, force),
            daemon=True,
        )
        t.start()

    def search_skills(self, query):
        """在缓存中搜索技能。"""
        if not self._cache:
            return []
        q = str(query or '').strip().lower()
        if not q:
            return list(self._cache.get('skills', []))
        return [
            s for s in self._cache.get('skills', [])
            if q in (s.get('name', '') or '').lower()
            or q in (s.get('description', '') or '').lower()
            or q in (s.get('id', '') or '').lower()
        ]

    @staticmethod
    def sanitize_marketplace_payload(payload):
        """将 skill.sh 格式转换为与 skills_index.json 兼容的内部格式。"""
        if not isinstance(payload, dict):
            return {'id': 'marketplace', 'updated_at': '', 'skills': []}
        skills = []
        seen_ids = set()
        for item in list(payload.get('skills', []) or []):
            if not isinstance(item, dict):
                continue
            skill_id = str(item.get('id', '') or '').strip()
            if not skill_id or skill_id in seen_ids:
                continue
            seen_ids.add(skill_id)
            skills.append({
                'id': skill_id,
                'name': str(item.get('name', '') or '').strip() or skill_id,
                'version': normalize_version(item.get('version', 'v0.0.0')),
                'description': str(item.get('description', '') or '').strip(),
                'min_app_version': normalize_version(item.get('min_app_version', 'v0.0.0')),
                'download_url': str(item.get('download_url', '') or '').strip(),
                'publisher': str(item.get('author', '') or item.get('publisher', '') or '').strip(),
                'homepage': str(item.get('homepage', '') or '').strip(),
                'global_hook': bool(item.get('global_hook', False)),
                'scene_bindings': list(item.get('scene_bindings', []) or []),
                'source': 'marketplace',
            })
        return {
            'id': 'marketplace',
            'updated_at': str(payload.get('updated_at', '') or '').strip(),
            'skills': skills,
        }

    def _worker(self, url, on_success, on_error, force):
        """后台线程：拉取 skill.sh 数据并回调 UI 线程。"""
        try:
            data = self._do_http_get(url)
            sanitized = self.sanitize_marketplace_payload(data)
            with self._lock:
                self._cache = sanitized
                self._cache_ts = time.time()
            self._save_cache()
            self._write_log('skill.sh 索引拉取成功')
            self._scheduler.after(0, lambda: on_success(sanitized))
        except Exception as exc:
            self._write_log(f'skill.sh 索引拉取失败: {exc}', level='WARN')
            cached = self._load_cache()
            if cached:
                with self._lock:
                    self._cache = cached
                    self._cache_ts = time.time()
                self._scheduler.after(0, lambda: on_success(cached))
            elif on_error:
                self._scheduler.after(0, lambda e=exc: on_error(e))

    def _do_http_get(self, url):
        """发起 HTTP GET 请求并解析 JSON。"""
        bust = f'{"&" if "?" in url else "?"}t={int(time.time())}'
        req = urllib.request.Request(url + bust, method='GET')
        req.add_header('User-Agent', 'PaperLab/1.0')
        req.add_header('Cache-Control', 'no-cache')
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw.decode('utf-8'))

    def _cache_path(self):
        return os.path.join(self._skills_root, CACHE_FILE_NAME)

    def _save_cache(self):
        try:
            path = self._cache_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with self._lock:
                data = self._cache
            if data:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_cache(self):
        try:
            path = self._cache_path()
            if not os.path.isfile(path):
                return None
            with open(path, 'r', encoding='utf-8') as f:
                return self.sanitize_marketplace_payload(json.load(f))
        except Exception:
            return None
