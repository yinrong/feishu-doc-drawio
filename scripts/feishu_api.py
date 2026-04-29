#!/usr/bin/env python3
"""Feishu Open API client for creating documents with rich text, tables, and whiteboards."""

import argparse
import json
import os
import sys
import time
from urllib.parse import quote

import requests

BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuAuth:
    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET")
        if not self.app_id or not self.app_secret:
            raise ValueError("FEISHU_APP_ID and FEISHU_APP_SECRET must be set")
        self._token = None
        self._expire_at = 0

    @property
    def token(self):
        if time.time() >= self._expire_at - 60:
            self._refresh()
        return self._token

    def _refresh(self):
        resp = requests.post(f"{BASE_URL}/auth/v3/tenant_access_token/internal", json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        })
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Auth failed: {data}")
        self._token = data["tenant_access_token"]
        self._expire_at = time.time() + data.get("expire", 7200)

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }


class FeishuDoc:
    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def _post(self, path, body=None, params=None, retries=3):
        for attempt in range(retries):
            resp = requests.post(f"{BASE_URL}{path}", headers=self.auth.headers, json=body, params=params)
            try:
                data = resp.json()
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"API error {path}: empty response (status {resp.status_code})")
            if data.get("code") != 0:
                raise RuntimeError(f"API error {path}: {data}")
            return data.get("data", {})
        raise RuntimeError(f"API error {path}: max retries exceeded")

    def _get(self, path, params=None, retries=3):
        for attempt in range(retries):
            resp = requests.get(f"{BASE_URL}{path}", headers=self.auth.headers, params=params)
            try:
                data = resp.json()
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"API error {path}: empty response (status {resp.status_code})")
            if data.get("code") != 0:
                raise RuntimeError(f"API error {path}: {data}")
            return data.get("data", {})
        raise RuntimeError(f"API error {path}: max retries exceeded")

    def _patch(self, path, body=None, params=None, retries=3):
        for attempt in range(retries):
            resp = requests.patch(f"{BASE_URL}{path}", headers=self.auth.headers, json=body, params=params)
            try:
                data = resp.json()
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(f"API error {path}: empty response (status {resp.status_code})")
            if data.get("code") != 0:
                raise RuntimeError(f"API error {path}: {data}")
            return data.get("data", {})
        raise RuntimeError(f"API error {path}: max retries exceeded")

    def create_document(self, title, folder_token=None):
        body = {"title": title}
        if folder_token:
            body["folder_token"] = folder_token
        data = self._post("/docx/v1/documents", body)
        doc = data["document"]
        return doc["document_id"], doc.get("revision_id")

    def transfer_owner(self, doc_id, email, remove_old_owner=False, old_owner_perm="full_access"):
        """Transfer document ownership to the user identified by Feishu email.

        Only email-based member_type is supported per project requirement.
        """
        if not email:
            return
        path = f"/drive/v1/permissions/{doc_id}/members/transfer_owner"
        params = {
            "type": "docx",
            "need_notification": "true",
            "remove_old_owner": "true" if remove_old_owner else "false",
            "old_owner_perm": old_owner_perm,
        }
        body = {"member_type": "email", "member_id": email}
        return self._post(path, body=body, params=params)

    def _add_children(self, doc_id, parent_id, children):
        return self._post(
            f"/docx/v1/documents/{doc_id}/blocks/{parent_id}/children",
            {"children": children},
            params={"document_revision_id": -1},
        )

    def _text_elements(self, elements):
        result = []
        for el in elements:
            if isinstance(el, str):
                result.append({"text_run": {"content": el, "text_element_style": {}}})
            elif isinstance(el, dict):
                style = {}
                if el.get("bold"):
                    style["bold"] = True
                if el.get("italic"):
                    style["italic"] = True
                if el.get("underline"):
                    style["underline"] = True
                if el.get("strikethrough"):
                    style["strikethrough"] = True
                if el.get("code"):
                    style["inline_code"] = True
                if el.get("link"):
                    style["link"] = {"url": el["link"]}
                result.append({
                    "text_run": {
                        "content": el.get("text", ""),
                        "text_element_style": style,
                    }
                })
        return result

    def add_heading(self, doc_id, parent_id, text, level=1):
        block_type = 2 + level  # heading1=3, heading2=4, ...
        field_name = f"heading{level}"
        return self._add_children(doc_id, parent_id, [{
            "block_type": block_type,
            field_name: {
                "elements": self._text_elements([text] if isinstance(text, str) else text),
                "style": {},
            },
        }])

    def add_text(self, doc_id, parent_id, elements):
        return self._add_children(doc_id, parent_id, [{
            "block_type": 2,
            "text": {
                "elements": self._text_elements(elements if isinstance(elements, list) else [elements]),
                "style": {},
            },
        }])

    def add_code_block(self, doc_id, parent_id, code, language="plain"):
        lang_map = {
            "python": 18, "java": 12, "javascript": 13, "typescript": 30,
            "go": 9, "rust": 22, "c": 3, "cpp": 4, "csharp": 5,
            "shell": 23, "bash": 23, "sql": 25, "json": 14, "xml": 33,
            "html": 11, "css": 6, "yaml": 34, "markdown": 16, "plain": 1,
        }
        return self._add_children(doc_id, parent_id, [{
            "block_type": 14,
            "code": {
                "elements": [{"text_run": {"content": code, "text_element_style": {}}}],
                "style": {"language": lang_map.get(language.lower(), 1)},
            },
        }])

    def add_bullet_list(self, doc_id, parent_id, items):
        children = []
        for item in items:
            children.append({
                "block_type": 12,
                "bullet": {
                    "elements": self._text_elements([item] if isinstance(item, str) else item),
                    "style": {},
                },
            })
        return self._add_children(doc_id, parent_id, children)

    def add_ordered_list(self, doc_id, parent_id, items):
        children = []
        for item in items:
            children.append({
                "block_type": 13,
                "ordered": {
                    "elements": self._text_elements([item] if isinstance(item, str) else item),
                    "style": {},
                },
            })
        return self._add_children(doc_id, parent_id, children)

    def add_divider(self, doc_id, parent_id):
        return self._add_children(doc_id, parent_id, [{"block_type": 22, "divider": {}}])

    def add_quote(self, doc_id, parent_id, elements):
        return self._add_children(doc_id, parent_id, [{
            "block_type": 15,
            "quote": {
                "elements": self._text_elements(elements if isinstance(elements, list) else [elements]),
                "style": {},
            },
        }])

    MAX_TABLE_ROWS = 9  # Feishu API limit (including header row)
    COL_WIDTH_MIN = 80
    COL_WIDTH_MAX = 500
    COL_WIDTH_PADDING = 32  # px added to the measured content width

    def add_table(self, doc_id, parent_id, headers, rows):
        """Create a table. Auto-splits into multiple sub-tables when rows exceed
        the Feishu API limit (9 rows including header). Each sub-table repeats
        the header row and gets column widths auto-fitted to its content."""
        if len(rows) + 1 > self.MAX_TABLE_ROWS:
            chunk = self.MAX_TABLE_ROWS - 1  # leave room for header
            ids = []
            for i in range(0, len(rows), chunk):
                ids.append(self._add_table_single(doc_id, parent_id, headers, rows[i:i + chunk]))
            return ids
        return self._add_table_single(doc_id, parent_id, headers, rows)

    def _add_table_single(self, doc_id, parent_id, headers, rows):
        row_count = len(rows) + 1  # +1 for header
        col_count = len(headers)

        time.sleep(0.5)
        result = self._add_children(doc_id, parent_id, [{
            "block_type": 31,
            "table": {
                "property": {"row_size": row_count, "column_size": col_count},
            },
        }])

        children = result.get("children", [])
        table_block = None
        for child in children:
            if child.get("block_type") == 31:
                table_block = child
                break

        if not table_block:
            raise RuntimeError("Table block not found in response")

        table_id = table_block["block_id"]
        block_data = self._get(f"/docx/v1/documents/{doc_id}/blocks/{table_id}",
                               params={"document_revision_id": -1})
        block = block_data.get("block", {})
        cells = block.get("table", {}).get("cells", [])

        all_values = headers + [cell for row in rows for cell in row]
        for i, cell_id in enumerate(cells):
            if i < len(all_values):
                value = str(all_values[i])
                style = {}
                if i < col_count:
                    style = {"bold": True}
                elements = [{"text_run": {"content": value, "text_element_style": style}}]
                self._add_children(doc_id, cell_id, [{
                    "block_type": 2,
                    "text": {"elements": elements, "style": {}},
                }])

        # Auto-fit column widths based on content
        widths = self._compute_column_widths(headers, rows)
        for col_index, width in enumerate(widths):
            self.update_table_column_width(doc_id, table_id, col_index, width)

        return table_id

    @classmethod
    def _compute_column_widths(cls, headers, rows):
        """Estimate per-column pixel width from content.

        Heuristic: CJK / wide chars count as 2 units, other chars as 1 unit;
        one unit ~= 9px at default Feishu font size. Result is clamped to
        [COL_WIDTH_MIN, COL_WIDTH_MAX] with COL_WIDTH_PADDING added."""
        widths = []
        for col_index in range(len(headers)):
            max_units = cls._text_units(str(headers[col_index]))
            for row in rows:
                if col_index < len(row):
                    max_units = max(max_units, cls._text_units(str(row[col_index])))
            width = max_units * 9 + cls.COL_WIDTH_PADDING
            width = max(cls.COL_WIDTH_MIN, min(cls.COL_WIDTH_MAX, int(width)))
            widths.append(width)
        return widths

    @staticmethod
    def _text_units(text):
        """Count display-width units. Wide (CJK, fullwidth) chars count as 2."""
        units = 0
        for ch in text:
            code = ord(ch)
            # CJK ideographs, hiragana/katakana, hangul, fullwidth forms, CJK punctuation
            if (0x4E00 <= code <= 0x9FFF or
                0x3400 <= code <= 0x4DBF or
                0x3000 <= code <= 0x303F or
                0x3040 <= code <= 0x30FF or
                0xAC00 <= code <= 0xD7AF or
                0xFF00 <= code <= 0xFFEF):
                units += 2
            else:
                units += 1
        return units

    def update_table_column_width(self, doc_id, table_block_id, column_index, width):
        """Set a single column's width (pixels) on an existing table block."""
        body = {
            "update_table_property": {
                "column_index": column_index,
                "column_width": int(width),
            },
        }
        return self._patch(
            f"/docx/v1/documents/{doc_id}/blocks/{table_block_id}",
            body=body,
            params={"document_revision_id": -1},
        )


class FeishuBoard:
    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def _post(self, path, body=None, retries=3):
        for attempt in range(retries):
            resp = requests.post(f"{BASE_URL}{path}", headers=self.auth.headers, json=body)
            if resp.status_code == 404:
                raise RuntimeError(
                    f"Board API 404 at {path}: 应用未开通 board:whiteboard 权限。"
                    f"请去飞书开放平台 → 应用 → 权限管理 添加权限后重新发布。"
                )
            try:
                data = resp.json()
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Board API error {path}: parse error "
                    f"(status {resp.status_code}, body={resp.text[:200]})"
                )
            if data.get("code") != 0:
                raise RuntimeError(f"Board API error {path}: {data}")
            return data.get("data", {})
        raise RuntimeError(f"Board API error {path}: max retries exceeded")

    def create_whiteboard(self, title):
        data = self._post("/board/v1/whiteboards", {"title": title})
        wb = data.get("whiteboard", {})
        return wb.get("whiteboard_id"), wb.get("url", "")

    # Feishu currently only accepts whiteboard content via the PlantUML endpoint
    # (per Feishu tech support). The older per-node / per-connector create API
    # does not work for writing content to new whiteboards.
    def add_plantuml(self, whiteboard_id, plant_uml_code,
                     style_type=1, syntax_type=1, diagram_type=0):
        """Render PlantUML (or Mermaid) source as editable whiteboard nodes.

        style_type: 1 = whiteboard (parsed to individual editable nodes),
                    2 = classic (single re-editable image).
        syntax_type: 1 = PlantUML, 2 = Mermaid.
        diagram_type: 0 = auto-detect (GML superset must be set to 201).
        """
        if not plant_uml_code or not plant_uml_code.strip():
            raise ValueError("plant_uml_code is empty")
        body = {
            "plant_uml_code": plant_uml_code,
            "style_type": style_type,
            "syntax_type": syntax_type,
            "diagram_type": diagram_type,
        }
        return self._post(
            f"/board/v1/whiteboards/{whiteboard_id}/nodes/plantuml",
            body=body,
        )


def process_blocks(auth, blocks, folder_token=None, default_owner_email=None):
    """Process a list of content blocks, creating docs and boards as needed.

    When default_owner_email is provided, ownership of every created document
    is transferred to that Feishu email immediately after creation.
    """
    doc_client = FeishuDoc(auth)
    board_client = FeishuBoard(auth)

    doc_title = "Untitled"
    doc_id = None
    results = {"documents": [], "whiteboards": []}

    def _create_doc_and_transfer(title):
        new_id, _ = doc_client.create_document(title, folder_token)
        url = f"https://bytedance.feishu.cn/docx/{new_id}"
        entry = {"id": new_id, "title": title, "url": url}
        if default_owner_email:
            doc_client.transfer_owner(new_id, default_owner_email)
            entry["owner"] = default_owner_email
        results["documents"].append(entry)
        return new_id

    for block in blocks:
        btype = block.get("type")

        if btype == "document_title":
            doc_title = block.get("text", "Untitled")
            continue

        # Lazily create document on first non-board block
        if doc_id is None and btype != "board":
            doc_id = _create_doc_and_transfer(doc_title)

        if btype == "heading":
            doc_client.add_heading(doc_id, doc_id, block.get("text", ""),
                                   level=block.get("level", 1))

        elif btype == "text":
            elements = block.get("elements", block.get("text", ""))
            doc_client.add_text(doc_id, doc_id, elements)

        elif btype == "code":
            doc_client.add_code_block(doc_id, doc_id,
                                      block.get("content", ""),
                                      block.get("language", "plain"))

        elif btype == "bullet_list":
            doc_client.add_bullet_list(doc_id, doc_id, block.get("items", []))

        elif btype == "ordered_list":
            doc_client.add_ordered_list(doc_id, doc_id, block.get("items", []))

        elif btype == "quote":
            doc_client.add_quote(doc_id, doc_id, block.get("elements", block.get("text", "")))

        elif btype == "divider":
            doc_client.add_divider(doc_id, doc_id)

        elif btype == "table":
            doc_client.add_table(doc_id, doc_id,
                                 block.get("headers", []),
                                 block.get("rows", []))

        elif btype == "board":
            wb_title = block.get("title", "Whiteboard")
            plantuml = block.get("plantuml", "").strip()
            if not plantuml:
                raise RuntimeError(
                    f"board block '{wb_title}' is missing required 'plantuml' field. "
                    f"Feishu whiteboards currently only accept content via PlantUML."
                )
            wb_id, wb_url = board_client.create_whiteboard(wb_title)
            board_client.add_plantuml(
                wb_id,
                plantuml,
                style_type=block.get("style_type", 1),
                syntax_type=block.get("syntax_type", 1),
                diagram_type=block.get("diagram_type", 0),
            )
            results["whiteboards"].append({"id": wb_id, "title": wb_title, "url": wb_url})

            # Add a link to the whiteboard in the document
            if doc_id:
                doc_client.add_text(doc_id, doc_id, [
                    {"text": f"📋 画板: {wb_title} → ", "bold": True},
                    {"text": wb_url, "link": wb_url},
                ])

    return results


def main():
    parser = argparse.ArgumentParser(description="Feishu document and whiteboard creator")
    sub = parser.add_subparsers(dest="command")

    p_doc = sub.add_parser("create-doc", help="Create a document with blocks")
    p_doc.add_argument("--title", required=True)
    p_doc.add_argument("--folder-token", default=None)
    p_doc.add_argument("--owner-email", default=None, help="Transfer ownership to this Feishu email after creation")
    p_doc.add_argument("--content-json", help="JSON string of blocks array")
    p_doc.add_argument("--content-file", help="Path to JSON file with blocks array")

    p_board = sub.add_parser("create-board", help="Create a whiteboard from PlantUML")
    p_board.add_argument("--title", required=True)
    p_board.add_argument("--plantuml", help="PlantUML source string")
    p_board.add_argument("--plantuml-file", help="Path to file containing PlantUML source")
    p_board.add_argument("--style-type", type=int, default=1,
                         help="1=whiteboard nodes (editable, default), 2=classic single image")
    p_board.add_argument("--syntax-type", type=int, default=1,
                         help="1=PlantUML (default), 2=Mermaid")
    p_board.add_argument("--diagram-type", type=int, default=0,
                         help="0=auto-detect (default); see Feishu docs for all values")

    p_all = sub.add_parser("create-all", help="Create document + whiteboards from blocks JSON")
    p_all.add_argument("--title", required=True)
    p_all.add_argument("--folder-token", default=None)
    p_all.add_argument("--owner-email", default=None, help="Transfer ownership to this Feishu email after creation")
    p_all.add_argument("--content-json", help="JSON string of blocks array")
    p_all.add_argument("--content-file", help="Path to JSON file with blocks array")
    p_all.add_argument("--stdin", action="store_true", help="Read content JSON from stdin")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    auth = FeishuAuth()

    if args.command == "create-doc":
        content = _load_content(args)
        blocks = [{"type": "document_title", "text": args.title}] + content.get("blocks", content if isinstance(content, list) else [])
        results = process_blocks(auth, blocks, args.folder_token, default_owner_email=args.owner_email)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.command == "create-board":
        if args.plantuml_file:
            with open(args.plantuml_file) as f:
                plantuml = f.read()
        elif args.plantuml:
            plantuml = args.plantuml
        else:
            raise SystemExit("create-board requires --plantuml or --plantuml-file")
        board = FeishuBoard(auth)
        wb_id, wb_url = board.create_whiteboard(args.title)
        board.add_plantuml(
            wb_id, plantuml,
            style_type=args.style_type,
            syntax_type=args.syntax_type,
            diagram_type=args.diagram_type,
        )
        print(json.dumps({"whiteboard_id": wb_id, "url": wb_url}, ensure_ascii=False, indent=2))

    elif args.command == "create-all":
        content = _load_content(args)
        blocks_list = content.get("blocks", content if isinstance(content, list) else [])
        blocks = [{"type": "document_title", "text": args.title}] + blocks_list
        results = process_blocks(auth, blocks, args.folder_token, default_owner_email=args.owner_email)
        print(json.dumps(results, ensure_ascii=False, indent=2))


def _load_content(args):
    if getattr(args, "stdin", False):
        return json.load(sys.stdin)
    if args.content_file:
        with open(args.content_file) as f:
            return json.load(f)
    if args.content_json:
        return json.loads(args.content_json)
    return {"blocks": []}


if __name__ == "__main__":
    main()
