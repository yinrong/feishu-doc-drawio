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

    def _post(self, path, body=None, params=None):
        resp = requests.post(f"{BASE_URL}{path}", headers=self.auth.headers, json=body, params=params)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"API error {path}: {data}")
        return data.get("data", {})

    def _get(self, path, params=None):
        resp = requests.get(f"{BASE_URL}{path}", headers=self.auth.headers, params=params)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"API error {path}: {data}")
        return data.get("data", {})

    def create_document(self, title, folder_token=None):
        body = {"title": title}
        if folder_token:
            body["folder_token"] = folder_token
        data = self._post("/docx/v1/documents", body)
        doc = data["document"]
        return doc["document_id"], doc.get("revision_id")

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
        return self._add_children(doc_id, parent_id, [{
            "block_type": block_type,
            "heading": {
                "elements": self._text_elements([text] if isinstance(text, str) else text),
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

    def add_table(self, doc_id, parent_id, headers, rows):
        row_count = len(rows) + 1  # +1 for header
        col_count = len(headers)

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

        return table_id


class FeishuBoard:
    def __init__(self, auth: FeishuAuth):
        self.auth = auth

    def _post(self, path, body=None):
        resp = requests.post(f"{BASE_URL}{path}", headers=self.auth.headers, json=body)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Board API error {path}: {data}")
        return data.get("data", {})

    def create_whiteboard(self, title):
        data = self._post("/board/v1/whiteboards", {"title": title})
        wb = data.get("whiteboard", {})
        return wb.get("whiteboard_id"), wb.get("url", "")

    def add_nodes(self, whiteboard_id, nodes):
        return self._post(f"/board/v1/whiteboards/{whiteboard_id}/nodes", {"nodes": nodes})

    def add_shape(self, wb_id, shape_type, x, y, w, h, text="",
                  fill_color="#FFFFFF", border_color="#000000"):
        node = {
            "type": "shape",
            "shape": {
                "shape_type": shape_type,
                "position": {"x": x, "y": y},
                "width": w,
                "height": h,
                "style": {
                    "fill_color": fill_color,
                    "border_color": border_color,
                    "border_width": 2,
                    "border_style": "solid",
                },
            },
        }
        if text:
            node["shape"]["text"] = {
                "content": text,
                "align": "center",
                "text_style": {"font_size": 14, "font_color": "#000000"},
            }
        data = self.add_nodes(wb_id, [node])
        nodes = data.get("nodes", [])
        return nodes[0]["id"] if nodes else None

    def add_connector(self, wb_id, start_id, end_id, label="",
                      connector_type="straight", end_arrow="arrow"):
        node = {
            "type": "connector",
            "connector": {
                "start_object_id": start_id,
                "end_object_id": end_id,
                "connector_type": connector_type,
                "style": {
                    "stroke_color": "#000000",
                    "stroke_width": 2,
                    "start_arrow": "none",
                    "end_arrow": end_arrow,
                },
            },
        }
        if label:
            node["connector"]["text"] = {"content": label}
        return self.add_nodes(wb_id, [node])

    def add_text_node(self, wb_id, x, y, content, font_size=14):
        node = {
            "type": "text",
            "text": {
                "position": {"x": x, "y": y},
                "content": content,
                "style": {"font_size": font_size, "font_color": "#333333"},
            },
        }
        data = self.add_nodes(wb_id, [node])
        nodes = data.get("nodes", [])
        return nodes[0]["id"] if nodes else None

    def build_flowchart(self, wb_id, spec):
        """Build a flowchart from a high-level spec.

        spec format:
        {
            "nodes": [
                {"id": "n1", "shape": "round_rectangle", "text": "Start", "x": 100, "y": 100,
                 "w": 180, "h": 60, "fill": "#E8F5E9", "border": "#4CAF50"},
                ...
            ],
            "connectors": [
                {"from": "n1", "to": "n2", "label": "", "type": "straight"},
                ...
            ]
        }
        """
        default_w = 180
        default_h = 60
        shape_colors = {
            "round_rectangle": ("#E8F5E9", "#4CAF50"),
            "rectangle": ("#E3F2FD", "#2196F3"),
            "diamond": ("#FFF3E0", "#FF9800"),
            "ellipse": ("#F3E5F5", "#9C27B0"),
            "triangle": ("#FFEBEE", "#F44336"),
            "parallelogram": ("#E0F7FA", "#00BCD4"),
        }

        id_map = {}

        for node in spec.get("nodes", []):
            shape = node.get("shape", "rectangle")
            fill, border = shape_colors.get(shape, ("#FFFFFF", "#000000"))
            real_id = self.add_shape(
                wb_id,
                shape_type=shape,
                x=node.get("x", 100),
                y=node.get("y", 100),
                w=node.get("w", default_w),
                h=node.get("h", default_h),
                text=node.get("text", ""),
                fill_color=node.get("fill", fill),
                border_color=node.get("border", border),
            )
            id_map[node["id"]] = real_id

        for conn in spec.get("connectors", []):
            src = id_map.get(conn["from"])
            dst = id_map.get(conn["to"])
            if src and dst:
                self.add_connector(
                    wb_id,
                    start_id=src,
                    end_id=dst,
                    label=conn.get("label", ""),
                    connector_type=conn.get("type", "straight"),
                )

        return id_map


def process_blocks(auth, blocks, folder_token=None):
    """Process a list of content blocks, creating docs and boards as needed."""
    doc_client = FeishuDoc(auth)
    board_client = FeishuBoard(auth)

    doc_title = "Untitled"
    doc_id = None
    results = {"documents": [], "whiteboards": []}

    for block in blocks:
        btype = block.get("type")

        if btype == "document_title":
            doc_title = block.get("text", "Untitled")
            continue

        # Lazily create document on first non-board block
        if doc_id is None and btype != "board":
            doc_id, _ = doc_client.create_document(doc_title, folder_token)
            doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"
            results["documents"].append({"id": doc_id, "title": doc_title, "url": doc_url})

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
            wb_id, wb_url = board_client.create_whiteboard(wb_title)
            results["whiteboards"].append({"id": wb_id, "title": wb_title, "url": wb_url})

            nodes_spec = block.get("nodes", [])
            if nodes_spec:
                flowchart_spec = {"nodes": [], "connectors": []}
                for n in nodes_spec:
                    if "connect" in n:
                        flowchart_spec["connectors"].append({
                            "from": n["connect"][0],
                            "to": n["connect"][1],
                            "label": n.get("label", ""),
                            "type": n.get("type", "straight"),
                        })
                    else:
                        flowchart_spec["nodes"].append(n)
                board_client.build_flowchart(wb_id, flowchart_spec)

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
    p_doc.add_argument("--content-json", help="JSON string of blocks array")
    p_doc.add_argument("--content-file", help="Path to JSON file with blocks array")

    p_board = sub.add_parser("create-board", help="Create a whiteboard with nodes")
    p_board.add_argument("--title", required=True)
    p_board.add_argument("--nodes-json", help="JSON string of flowchart spec")
    p_board.add_argument("--nodes-file", help="Path to JSON file with flowchart spec")

    p_all = sub.add_parser("create-all", help="Create document + whiteboards from blocks JSON")
    p_all.add_argument("--title", required=True)
    p_all.add_argument("--folder-token", default=None)
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
        results = process_blocks(auth, blocks, args.folder_token)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.command == "create-board":
        spec = _load_nodes(args)
        board = FeishuBoard(auth)
        wb_id, wb_url = board.create_whiteboard(args.title)
        board.build_flowchart(wb_id, spec)
        print(json.dumps({"whiteboard_id": wb_id, "url": wb_url}, ensure_ascii=False, indent=2))

    elif args.command == "create-all":
        content = _load_content(args)
        blocks_list = content.get("blocks", content if isinstance(content, list) else [])
        blocks = [{"type": "document_title", "text": args.title}] + blocks_list
        results = process_blocks(auth, blocks, args.folder_token)
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


def _load_nodes(args):
    if args.nodes_file:
        with open(args.nodes_file) as f:
            return json.load(f)
    if args.nodes_json:
        return json.loads(args.nodes_json)
    return {"nodes": [], "connectors": []}


if __name__ == "__main__":
    main()
